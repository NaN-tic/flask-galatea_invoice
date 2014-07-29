from flask import Blueprint, render_template, current_app, abort, g, \
    url_for, request, session, send_file
from galatea.tryton import tryton
from galatea.utils import slugify
from galatea.helpers import login_required
from flask.ext.babel import gettext as _, lazy_gettext as __
from flask.ext.paginate import Pagination
import tempfile

invoice = Blueprint('invoice', __name__, template_folder='templates')

DISPLAY_MSG = __('Displaying <b>{start} - {end}</b> {record_name} of <b>{total}</b>')

LIMIT = current_app.config.get('TRYTON_PAGINATION_INVOICE_LIMIT', 20)
INVOICE_REPORT = current_app.config.get('TRYTON_INVOICE_REPORT', 'account.invoice')
STATE_EXCLUDE = current_app.config.get('TRYTON_INVOICE_STATE_EXCLUDE')

Invoice = tryton.pool.get('account.invoice')
InvoiceReport = tryton.pool.get('account.invoice', type='report')

INVOICE_FIELD_NAMES = [
    'create_date', 'invoice_date', 'number', 'reference', 'description',
    'state', 'type', 'untaxed_amount', 'tax_amount', 'total_amount',
    ]

@invoice.route("/print/<id>", endpoint="invoice_print")
@login_required
@tryton.transaction()
def invoice_print(lang, id):
    '''Invoice Print'''

    invoices = Invoice.search_read([
        ('id', '=', id),
        ('party', '=', session['customer']),
        ], limit=1, fields_names=['number'])
    
    if not invoices:
        abort(404)

    invoice, = invoices

    _, report, _, _ = InvoiceReport.execute([invoice['id']], {})
    report_name = 'invoice-%s.pdf' % (slugify(invoice.get('number')) or 'invoice')

    with tempfile.NamedTemporaryFile(
            prefix='%s-' % current_app.config['TRYTON_DATABASE'],
            suffix='.pdf', delete=False) as temp:
        temp.write(report)
    temp.close()
    data = open(temp.name, 'rb')

    return send_file(data, attachment_filename=report_name, as_attachment=True)

@invoice.route("/<id>", endpoint="invoice")
@login_required
@tryton.transaction()
def invoice_detail(lang, id):
    '''Invoice Detail'''

    invoices = Invoice.search([
        ('id', '=', id),
        ('party', '=', session['customer']),
        ], limit=1)
    if not invoices:
        abort(404)

    invoice, = Invoice.browse(invoices)

    #breadcumbs
    breadcrumbs = [{
        'slug': url_for('my-account', lang=g.language),
        'name': _('My Account'),
        }, {
        'slug': url_for('.invoices', lang=g.language),
        'name': _('Invoices'),
        }, {
        'slug': url_for('.invoice', lang=g.language, id=invoice.id),
        'name': invoice.number or _('Not number'),
        }]

    return render_template('invoice.html',
            breadcrumbs=breadcrumbs,
            invoice=invoice,
            )

@invoice.route("/", endpoint="invoices")
@login_required
@tryton.transaction()
def invoice_list(lang):
    '''Invoices'''

    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1

    domain = [
        ('party', '=', session['customer']),
        ('state', 'not in', STATE_EXCLUDE),
        ]
    total = Invoice.search_count(domain)
    offset = (page-1)*LIMIT

    order = [
        ('invoice_date', 'DESC'),
        ('id', 'DESC'),
        ]
    invoices = Invoice.search_read(
        domain, offset, LIMIT, order, INVOICE_FIELD_NAMES)

    pagination = Pagination(
        page=page, total=total, per_page=LIMIT, display_msg=DISPLAY_MSG, bs_version='3')

    #breadcumbs
    breadcrumbs = [{
        'slug': url_for('my-account', lang=g.language),
        'name': _('My Account'),
        }, {
        'slug': url_for('.invoices', lang=g.language),
        'name': _('Invoices'),
        }]

    return render_template('invoices.html',
            breadcrumbs=breadcrumbs,
            pagination=pagination,
            invoices=invoices,
            )
