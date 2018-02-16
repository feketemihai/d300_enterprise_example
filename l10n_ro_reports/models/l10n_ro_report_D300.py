# -*- coding: utf-8 -*-

import time
from odoo import api, fields, models, _
from odoo.tools.misc import formatLang
from odoo.exceptions import UserError
from odoo.addons.web.controllers.main import clean_action


class RomaniaReportD300(models.AbstractModel):
    _name = "l10n.ro.report.D300"
    _description = "Decont TVA"
    _inherit = 'account.report'
    
    filter_date = {'date_from': '', 'date_to': '', 'filter': 'this_month'}
    filter_all_entries = False    

    def get_columns_name(self, options):
        return [{'name': _('Tag Code')}, {'name': _('Tag Name')},
                {'name': _('Net Amount'), 'class': 'number'},
                {'name': _('Tax Amount'), 'class': 'number'}]

    @api.model
    def get_lines(self, options, line_id=None):
        lines = []
        tables, where_clause, where_params = \
            self.env['account.move.line'].with_context(
                strict_range=True)._query_get()
        tax_tags = self.env['account.account.tag'].search(
            [('applicability', '=', 'taxes')])
        if where_clause:
            where_clause = 'AND ' + where_clause

        if line_id != None:
            where_clause = 'AND tag.id = %s' + where_clause
            where_params = [line_id] + where_params
            unfold_query = """
                select tag.id as tagid, tax.name, tax.id,
                    abs(coalesce(sum(movetax.tax_base_amount), 0.00)) AS net,
                    abs(coalesce(sum(movetax.balance), 0.00)) AS tax
                from
                    account_account_tag as tag
                    left join account_tax_account_tag as taxtag on tag.id = taxtag.account_account_tag_id
                    left join account_tax as tax on tax.id = taxtag.account_tax_id
                    left join """ + tables + """ as movetax on movetax.tax_line_id = tax.id
                where tag.id is not null AND movetax.tax_exigible""" + where_clause + """
                group by tag.id, tax.id
                order by tax.name
            """
        sql_query = """
            select replace(tag.name, 'Romania - D300: randul ', '') as code, tag.name, tag.id,
                abs(coalesce(sum(movetax.tax_base_amount), 0.00)) AS net,
                abs(coalesce(sum(movetax.balance), 0.00)) AS tax
            from
                account_account_tag as tag
                left join account_tax_account_tag as taxtag on tag.id = taxtag.account_account_tag_id
                left join account_tax as tax on tax.id = taxtag.account_tax_id
                left join """ + tables + """ as movetax on movetax.tax_line_id = tax.id
            where tag.id is not null AND movetax.tax_exigible""" + where_clause + """
            group by tag.id
            order by code, tag.name
        """
        params = where_params
        self.env.cr.execute(sql_query, where_params)
        results = self.env.cr.dictfetchall()

        for line in results:
            lines.append({
                'id': line.get('id'),
                'code': line.get('code'),
                'name': line.get('name'),
                'level': 2,
                'unfoldable': True,
                'unfolded': line_id == line.get('id') and True or False,
                'columns': [{'name': line.get('net')}, {'name': line.get('tax')}],
            })
        if line_id:
            self.env.cr.execute(unfold_query, params)
            results = self.env.cr.dictfetchall()
            for child_line in results:
                lines.append({
                    'id': '%s_%s' % (child_line.get('id'), child_line.get('name')),
                    'name': child_line.get('name'),
                    'level': 4,
                    'caret_options': 'movelines',                        
                    'parent_id': line_id,
                    'columns': [{'name': child_line.get('net')},
                                {'name': child_line.get('tax')}],
                })
        return lines

    def get_report_name(self):
        return _('Decont TVA - D300')

    def get_templates(self):
        templates = super(RomaniaReportD300, self).get_templates()
        templates['main_template'] = 'l10n_ro_report_D300.template_tag_report'
        templates['line_template'] = 'l10n_ro_report_D300.line_template_tag_report'
        return templates

    def open_tax_lines(self, options, params):
        tax_id = int(params.get('id').split('_')[0])
        [action] = self.env.ref('account.action_move_line_select_tax_audit').read()
        action['context'] = self.env.context
        action['domain'] = [
            ('tax_line_id', '=', tax_id),
            ('tax_exigible', '=', True),
            ('date', '<=', options.get('date').get('date_to')),
            ('date', '>=', options.get('date').get('date_from'))
        ]
        action = clean_action(action)
        return action
