from trytond.modules.voyager import slugify
from flask import Blueprint, render_template, current_app, abort, g, \
    url_for, request, session, send_file
from app_extensions import tryton
from galatea.helpers import login_required, customer_required
from flask_babel import gettext as _, lazy_gettext
from flask_paginate import Pagination
import tempfile

invoice = Blueprint('invoice', __name__, template_folder='templates')

DISPLAY_MSG = lazy_gettext('Displaying <b>{start} - {end}</b> of <b>{total}</b>')

def _limit():
    return current_app.config.get('TRYTON_PAGINATION_INVOICE_LIMIT', 20)


def _state_exclude():
    return current_app.config.get('TRYTON_INVOICE_STATE_EXCLUDE', [])


def _state_invoice_print():
    return current_app.config.get('TRYTON_INVOICE_PRINT', ['paid'])


@invoice.route("/print/<int:id>", endpoint="invoice_print")
@login_required
@customer_required
@tryton.transaction()
def invoice_print(lang, id):
    '''Invoice Print'''
    Invoice = tryton.pool.get('account.invoice')
    report_name = current_app.config.get('TRYTON_INVOICE_REPORT', 'account.invoice')
    InvoiceReport = tryton.pool.get(report_name, type='report')

    domain = [
        ('id', '=', id),
        ('state', 'in', _state_invoice_print()),
        ]
    if not session.get('manager', False):
        domain.append(('party', '=', session['customer']))
    invoices = Invoice.search(domain, limit=1)

    if not invoices:
        abort(404)

    invoice, = invoices

    _, report, _, _ = InvoiceReport.execute([invoice.id], {})
    report_name = 'invoice-%s.pdf' % (slugify(invoice.number) or 'invoice')

    with tempfile.NamedTemporaryFile(
            prefix='%s-' % current_app.config['TRYTON_DATABASE'],
            suffix='.pdf', delete=False) as temp:
        temp.write(report)
    temp.close()
    data = open(temp.name, 'rb')

    return send_file(data, download_name=report_name, as_attachment=True)

@invoice.route("/<int:id>", endpoint="invoice")
@login_required
@customer_required
@tryton.transaction()
def invoice_detail(lang, id):
    '''Invoice Detail'''
    Invoice = tryton.pool.get('account.invoice')

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
@customer_required
@tryton.transaction()
def invoice_list(lang):
    '''Invoices'''
    Invoice = tryton.pool.get('account.invoice')
    limit = _limit()

    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1

    domain = [
        ('party', '=', session['customer']),
        ('state', 'not in', _state_exclude()),
        ]
    total = Invoice.search_count(domain)
    offset = (page-1)*limit

    order = [
        ('invoice_date', 'DESC'),
        ('id', 'DESC'),
        ]
    invoices = Invoice.search(domain, offset, limit, order)

    pagination = Pagination(
        page=page, total=total, per_page=limit, display_msg=DISPLAY_MSG, bs_version='3')

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
