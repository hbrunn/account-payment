# -*- coding: utf-8 -*-
# © 2015 Eficent Business and IT Consulting Services S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from openerp import api, fields, models, SUPERUSER_ID, _
import datetime
from lxml import etree


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    days_overdue = fields.Integer(compute='_compute_days_overdue',
                                  search='_search_days_overdue',
                                  string='Days overdue')
    overdue_term_last = fields.Float(string='> Last overdue term')

    @api.multi
    @api.depends('date_maturity')
    def _compute_days_overdue(self):
        today_date = fields.Date.from_string(fields.Date.today())
        for line in self:
            if line.date_maturity and line.amount_residual:
                date_maturity = fields.Date.from_string(
                    line.date_maturity)
                days_overdue = (today_date - date_maturity).days
                if days_overdue > 0:
                    line.days_overdue = days_overdue

    def _search_days_overdue(self, operator, value):
        due_date = fields.Date.from_string(fields.Date.today()) - \
                   datetime.timedelta(days=value)
        if operator in ('!=', '<>', 'in', 'not in'):
            raise ValueError('Invalid operator: %s' % (operator,))
        if operator == '>':
            operator = '<'
        elif operator == '<':
            operator = '>'
        elif operator == '>=':
            operator = '<='
        elif operator == '<=':
            operator = '>='
        return [('date_maturity', operator, due_date)]

    @api.multi
    @api.depends('date_maturity')
    def _compute_overdue_terms(self):
        today_date = fields.Date.from_string(fields.Date.today())
        overdue_terms = self.env['account.overdue.term'].search([])
        for line in self:
            for tech_name in overdue_terms:
                line[tech_name] = 0.0
            if line.date_maturity and line.amount_residual:
                date_maturity = fields.Date.from_string(
                    line.date_maturity)
                days_overdue = (today_date - date_maturity).days

                for overdue_term in overdue_terms:
                    if overdue_term.from_day > days_overdue > \
                            overdue_term.to_day and line.amount_residual > 0.0:
                        line[overdue_term.tech_name] = line.amount_residual
                if all(line[term.tech_name] == 0.0 for term in overdue_terms) and\
                        line.amount_residual > 0.0:
                    line.overdue_term_last = line.amount_residual

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False,
                        submenu=False):
        result = super(AccountMoveLine, self).fields_view_get(view_id,
                                                              view_type,
                                                              toolbar=toolbar,
                                                              submenu=submenu)
        overdue_terms = self.env['account.overdue.term'].search(
            [], order='from_day ASC')

        doc = etree.XML(result['arch'])
        if result['model'] == 'account.move.line' and result['type'] == 'tree':
            placeholder = doc.xpath("//field[@name='days_overdue']")
            if placeholder:
                placeholder = placeholder[0]
                for overdue_term in overdue_terms:
                    placeholder.addnext(etree.Element(
                        'field', {'name': str(overdue_term.tech_name)}))
                    result['fields'].update({
                        overdue_term.tech_name: {'domain': [],
                                                 'string': overdue_term.name,
                                                 'readonly': False,
                                                 'context': {},
                                                 'type': 'float'}})
                result['arch'] = etree.tostring(doc)
        return result

    def _register_hook(self, cr):
        term_obj = self.pool['account.overdue.term']
        term_ids = term_obj.search(cr, SUPERUSER_ID, [])
        for term in  term_obj.browse(cr, SUPERUSER_ID, term_ids):
            field_name = term.tech_name
            # register_hook can be called multiple times
            if field_name in self._fields:
                continue
            self._fields[field_name] = fields.Float(
                string=term.name, compute='_compute_overdue_terms')
        self._setup_fields(cr, SUPERUSER_ID)
        self._setup_complete(cr, SUPERUSER_ID)
        return super(AccountMoveLine, self)._register_hook(cr)
