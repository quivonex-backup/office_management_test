import 'package:flutter/material.dart';

import '../../constants/app_constants.dart';
import '../../services/other_services/visitors_service.dart';
import '../../utils/helpers.dart';
import '../../utils/validators.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/dialogs/app_dialogs.dart';
import '../../widgets/forms/opt.dart';
import '../generic/crud_list_screen.dart';
import '../generic/crud_models.dart';
import '../generic/lookups.dart';

String _j(Iterable<dynamic> parts) => parts.where((e) => e != null && '$e'.trim().isNotEmpty).join(' · ');

class FrontDeskScreen extends StatelessWidget {
  const FrontDeskScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Front desk',
          createLabel: 'Check in visitor',
          list: (f) => VisitorsService.list(f),
          create: (b, files) => VisitorsService.create(b, photo: files.isEmpty ? null : files.first),
          update: (i, b, files) => VisitorsService.update(i['id'] as int, b, photo: files.isEmpty ? null : files.first),
          deactivate: (i) => VisitorsService.deactivate(i['id'] as int),
          deactivateLabel: 'Remove entry',
          managePerms: const ['visitor.manage'],
          filters: [FilterSpec('inside_only', 'Who', options: const [Opt(true, 'Inside now')])],
          titleOf: (i) => '${i['visitor_name']}${i['visitor_company'] != null ? ' (${i['visitor_company']})' : ''}',
          subtitleOf: (i) => _j([
            Fmt.label(i['purpose'] as String?),
            'Host: ${(i['host'] as Map?)?['full_name'] ?? '—'}',
            'In ${Fmt.dateTime(i['check_in_at'])}',
            if (i['check_out_at'] != null) 'Out ${Fmt.dateTime(i['check_out_at'])}',
          ]),
          badgeOf: (i) => i['is_inside'] == true ? 'INSIDE' : 'LEFT',
          rowActions: [
            RowAction('Check out', Icons.logout, (c, i) async {
              final ok = await AppDialogs.confirm(c, title: 'Check out visitor?', message: '${i['visitor_name']}', confirmLabel: 'Check out');
              if (!ok || !c.mounted) return false;
              final r = await VisitorsService.checkOut(i['id'] as int);
              if (c.mounted) Toast.result(c, r, success: 'Visitor checked out.');
              return r.ok;
            }, visible: (i) => i['is_inside'] == true),
          ],
          fields: [
            FieldSpec('visitor_name', 'Visitor name', required: true, validator: (v) => Validators.name(v, label: 'Name', required: true)),
            FieldSpec('visitor_mobile', 'Mobile', type: FieldType.phone, required: true, validator: (v) => Validators.mobile(v, required: true)),
            const FieldSpec('visitor_email', 'Email', type: FieldType.email),
            const FieldSpec('visitor_company', 'Company'),
            const FieldSpec('visitor_count', 'Number of people', type: FieldType.integer, initial: 1),
            FieldSpec('purpose', 'Purpose', type: FieldType.dropdown, required: true, initial: 'MEETING', options: Lookups.strings(AppConstants.visitPurposes)),
            const FieldSpec('purpose_note', 'Purpose note'),
            FieldSpec('host_id', 'Host (employee)', type: FieldType.dropdown, loadOptions: Lookups.employees, clearable: true, readValue: (i) => (i['host'] as Map?)?['id']),
            FieldSpec('id_proof_type', 'ID proof', type: FieldType.dropdown, options: Lookups.strings(AppConstants.idTypes)),
            const FieldSpec('badge_number', 'Badge number'),
            const FieldSpec('vehicle_number', 'Vehicle number'),
            const FieldSpec('notes', 'Notes', type: FieldType.multiline),
            const FieldSpec('photo', 'Photo', type: FieldType.image),
          ],
        ),
      );
}

class MyVisitorsScreen extends StatelessWidget {
  const MyVisitorsScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'My visitors',
          hasSearch: false,
          list: (f) => VisitorsService.myVisitors(f),
          titleOf: (i) => '${i['visitor_name']}${i['visitor_company'] != null ? ' (${i['visitor_company']})' : ''}',
          subtitleOf: (i) => _j([Fmt.label(i['purpose'] as String?), i['visitor_mobile'], 'In ${Fmt.dateTime(i['check_in_at'])}']),
        ),
      );
}
