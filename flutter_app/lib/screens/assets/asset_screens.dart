import 'package:flutter/material.dart';

import '../../constants/app_constants.dart';
import '../../services/other_services/assets_service.dart';
import '../../utils/helpers.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/dialogs/app_dialogs.dart';
import '../generic/crud_form_screen.dart';
import '../generic/crud_list_screen.dart';
import '../generic/crud_models.dart';
import '../generic/lookups.dart';

String _j(Iterable<dynamic> parts) => parts.where((e) => e != null && '$e'.trim().isNotEmpty).join(' · ');

class AssetCategoriesScreen extends StatelessWidget {
  const AssetCategoriesScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Asset categories',
          hasSearch: false,
          activeFilterKey: 'include_inactive',
          list: (f) => AssetsService.categoryList(includeInactive: f['include_inactive'] == true),
          create: (b, _) => AssetsService.categoryCreate('${b['name']}', description: b['description'] as String?),
          update: (i, b, _) => AssetsService.categoryUpdate(i['id'] as int, b),
          deactivate: (i) => AssetsService.categoryDeactivate(i['id'] as int),
          managePerms: const ['asset.manage'],
          titleOf: (i) => '${i['name']}',
          subtitleOf: (i) => '${i['asset_count'] ?? 0} assets',
          fields: const [FieldSpec('name', 'Name', required: true), FieldSpec('description', 'Description', type: FieldType.multiline)],
        ),
      );
}

class AssetsScreen extends StatelessWidget {
  const AssetsScreen({super.key});

  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Asset register',
          list: (f) => AssetsService.assetList(f),
          create: (b, _) => AssetsService.assetCreate(b),
          update: (i, b, _) => AssetsService.assetUpdate(i['id'] as int, b),
          deactivate: (i) => AssetsService.assetDeactivate(i['id'] as int),
          managePerms: const ['asset.manage'],
          filters: [
            FilterSpec('status', 'Status', options: Lookups.strings(AppConstants.assetStatuses)),
            FilterSpec('category_id', 'Category', loadOptions: Lookups.assetCategories),
          ],
          header: (ctx, r) {
            final s = (r.raw['summary'] as Map?) ?? const {};
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
              child: Align(alignment: Alignment.centerLeft, child: Text('${s['total'] ?? 0} assets', style: Theme.of(ctx).textTheme.bodySmall)),
            );
          },
          titleOf: (i) => '${i['asset_code']}  ${i['name']}',
          subtitleOf: (i) => _j([(i['category'] as Map?)?['name'], i['brand'], i['serial_number'], (i['current_holder'] as Map?)?['full_name']]),
          badgeOf: (i) => i['status'] as String?,
          rowActions: [
            RowAction('Assign to employee', Icons.person_add_alt, (c, i) async {
              final saved = await Navigator.push<bool>(
                c,
                MaterialPageRoute(
                  builder: (_) => CrudFormScreen(
                    title: 'Assign ${i['name']}',
                    fields: [
                      FieldSpec('employee_id', 'Employee', type: FieldType.dropdown, required: true, loadOptions: Lookups.employees),
                      FieldSpec('assigned_on', 'Assigned on', type: FieldType.date, initial: Fmt.apiDate(DateTime.now())),
                      FieldSpec('condition', 'Condition', type: FieldType.dropdown, options: Lookups.strings(AppConstants.conditions)),
                      const FieldSpec('note', 'Note', type: FieldType.multiline),
                    ],
                    onSubmit: (b, f) => AssetsService.assetAssign({'asset_id': i['id'], ...b}),
                  ),
                ),
              );
              return saved == true;
            }, visible: (i) => i['status'] == 'AVAILABLE'),
            RowAction('Return asset', Icons.assignment_return_outlined, (c, i) async {
              final saved = await Navigator.push<bool>(
                c,
                MaterialPageRoute(
                  builder: (_) => CrudFormScreen(
                    title: 'Return ${i['name']}',
                    fields: [
                      FieldSpec('returned_on', 'Returned on', type: FieldType.date, initial: Fmt.apiDate(DateTime.now())),
                      FieldSpec('condition', 'Condition', type: FieldType.dropdown, options: Lookups.strings(AppConstants.conditions)),
                      FieldSpec('status_after', 'Status after return', type: FieldType.dropdown, initial: 'AVAILABLE', options: Lookups.strings(AppConstants.editableAssetStatuses)),
                      const FieldSpec('note', 'Note', type: FieldType.multiline),
                    ],
                    onSubmit: (b, f) => AssetsService.assetReturn({'asset_id': i['id'], ...b}),
                  ),
                ),
              );
              return saved == true;
            }, visible: (i) => i['status'] == 'ASSIGNED'),
            RowAction('Assignment history', Icons.history, (c, i) async {
              final r = await AssetsService.assetDetail(i['id'] as int);
              if (!c.mounted) return false;
              if (!r.ok) {
                Toast.result(c, r);
                return false;
              }
              final rows = asMapList(asMap(r.data)['assignments']);
              AppDialogs.info(
                c,
                '${i['name']}',
                rows.isEmpty
                    ? 'Never assigned.'
                    : rows.map((a) => '${(a['employee'] as Map?)?['full_name']}\n  ${Fmt.date(a['assigned_on'])} → ${a['returned_on'] == null ? 'now' : Fmt.date(a['returned_on'])}').join('\n\n'),
              );
              return false;
            }),
          ],
          fields: [
            const FieldSpec('name', 'Name', required: true),
            FieldSpec('category_id', 'Category', type: FieldType.dropdown, required: true, loadOptions: Lookups.assetCategories, readValue: (i) => (i['category'] as Map?)?['id']),
            const FieldSpec('brand', 'Brand'),
            const FieldSpec('model_number', 'Model number'),
            const FieldSpec('serial_number', 'Serial number'),
            FieldSpec('branch_id', 'Branch', type: FieldType.dropdown, loadOptions: Lookups.branches, clearable: true, readValue: (i) => (i['branch'] as Map?)?['id']),
            FieldSpec('status', 'Status', type: FieldType.dropdown, editOnly: true, options: Lookups.strings(AppConstants.editableAssetStatuses)),
            const FieldSpec('purchase_date', 'Purchase date', type: FieldType.date),
            const FieldSpec('purchase_cost', 'Purchase cost', type: FieldType.decimal),
            const FieldSpec('warranty_until', 'Warranty until', type: FieldType.date),
            const FieldSpec('notes', 'Notes', type: FieldType.multiline),
          ],
        ),
      );
}

class MyAssetsScreen extends StatelessWidget {
  const MyAssetsScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'My assets',
          hasSearch: false,
          list: (_) => AssetsService.myAssets(),
          titleOf: (i) => '${i['asset_code']}  ${i['name']}',
          subtitleOf: (i) => _j([(i['category'] as Map?)?['name'], i['brand'], i['serial_number'], 'since ${Fmt.date(i['assigned_on'])}']),
        ),
      );
}
