import 'package:flutter/material.dart';

import '../../api/api_request.dart';
import '../../constants/app_constants.dart';
import '../../services/other_services/helpdesk_service.dart';
import '../../utils/helpers.dart';
import '../../widgets/buttons/primary_button.dart';
import '../../widgets/cards/info_card.dart';
import '../../widgets/common/api_builder.dart';
import '../../widgets/common/status_badge.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/dialogs/app_dialogs.dart';
import '../../widgets/forms/opt.dart';
import '../../widgets/navigation/app_scaffold.dart';
import '../generic/crud_list_screen.dart';
import '../generic/crud_models.dart';
import '../generic/lookups.dart';

String _ticketTitle(Item i) => '${i['ticket_code'] ?? ''}  ${i['subject'] ?? ''}'.trim();
String _ticketSub(Item i) {
  final parts = <String>[
    if ((i['category'] as Map?)?['name'] != null) '${(i['category'] as Map)['name']}',
    'Priority ${Fmt.label(i['priority'] as String?)}',
    if ((i['raised_by'] as Map?)?['full_name'] != null) 'by ${(i['raised_by'] as Map)['full_name']}',
    if ((i['assigned_to'] as Map?)?['full_name'] != null) '→ ${(i['assigned_to'] as Map)['full_name']}' else 'Unassigned',
  ];
  return parts.join(' · ');
}

void _openTicket(BuildContext c, Item i, Future<void> Function() reload) async {
  await Navigator.push(c, MaterialPageRoute(builder: (_) => TicketDetailScreen(ticketId: i['id'] as int)));
  reload();
}

class MyTicketsScreen extends StatelessWidget {
  const MyTicketsScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'My tickets',
          hasSearch: false,
          createLabel: 'Raise ticket',
          list: (f) => HelpdeskService.myTickets(view: (f['view'] ?? 'raised') as String, status: f['status'] as String?),
          create: (b, files) => HelpdeskService.ticketCreate(b, attachment: files.isEmpty ? null : files.first),
          filters: [
            FilterSpec('view', 'Show', options: const [Opt('raised', 'Raised by me'), Opt('assigned', 'Assigned to me')]),
            FilterSpec('status', 'Status', options: Lookups.strings(AppConstants.ticketStatuses)),
          ],
          titleOf: _ticketTitle,
          subtitleOf: _ticketSub,
          badgeOf: (i) => i['status'] as String?,
          onTap: _openTicket,
          fields: [
            const FieldSpec('subject', 'Subject', required: true),
            const FieldSpec('description', 'Describe the problem', type: FieldType.multiline, required: true),
            FieldSpec('category_id', 'Category', type: FieldType.dropdown, required: true, loadOptions: Lookups.ticketCategories),
            FieldSpec('priority', 'Priority', type: FieldType.dropdown, required: true, initial: 'MEDIUM', options: Lookups.strings(AppConstants.ticketPriorities)),
            const FieldSpec('attachment', 'Attachment', type: FieldType.file),
          ],
        ),
      );
}

class HelpdeskQueueScreen extends StatelessWidget {
  const HelpdeskQueueScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Helpdesk queue',
          list: (f) => HelpdeskService.ticketList(f),
          filters: [
            FilterSpec('status', 'Status', options: Lookups.strings(AppConstants.ticketStatuses)),
            FilterSpec('priority', 'Priority', options: Lookups.strings(AppConstants.ticketPriorities)),
            FilterSpec('category_id', 'Category', loadOptions: Lookups.ticketCategories),
          ],
          header: (ctx, r) {
            final s = (r.raw['summary'] as Map?) ?? const {};
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text('${s['total'] ?? 0} tickets · ${s['unassigned_open'] ?? 0} unassigned open', style: Theme.of(ctx).textTheme.bodySmall),
              ),
            );
          },
          titleOf: _ticketTitle,
          subtitleOf: _ticketSub,
          badgeOf: (i) => i['status'] as String?,
          onTap: _openTicket,
        ),
      );
}

class TicketCategoriesScreen extends StatelessWidget {
  const TicketCategoriesScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Ticket categories',
          hasSearch: false,
          activeFilterKey: 'include_inactive',
          list: (f) => HelpdeskService.categoryList(includeInactive: f['include_inactive'] == true),
          create: (b, _) => HelpdeskService.categoryCreate(b),
          update: (i, b, _) => HelpdeskService.categoryUpdate(i['id'] as int, b),
          deactivate: (i) => HelpdeskService.categoryDeactivate(i['id'] as int),
          managePerms: const ['ticket.manage'],
          titleOf: (i) => '${i['name']}',
          subtitleOf: (i) => '${(i['department'] as Map?)?['name'] ?? 'Any department'} · ${(i['default_assignee'] as Map?)?['full_name'] ?? 'No default assignee'} · ${i['open_tickets'] ?? 0} open',
          fields: [
            const FieldSpec('name', 'Name', required: true),
            const FieldSpec('description', 'Description', type: FieldType.multiline),
            FieldSpec('department_id', 'Department', type: FieldType.dropdown, loadOptions: Lookups.departments, clearable: true, readValue: (i) => (i['department'] as Map?)?['id']),
            FieldSpec('default_assignee_id', 'Default assignee', type: FieldType.dropdown, loadOptions: Lookups.employees, clearable: true, readValue: (i) => (i['default_assignee'] as Map?)?['id']),
          ],
        ),
      );
}

/// Ticket with comments; status moves, assignment and comments are shown only when the
/// server says they are allowed (`allowed_actions`).
class TicketDetailScreen extends StatefulWidget {
  final int ticketId;
  const TicketDetailScreen({super.key, required this.ticketId});
  @override
  State<TicketDetailScreen> createState() => _TicketDetailScreenState();
}

class _TicketDetailScreenState extends State<TicketDetailScreen> {
  Key _k = UniqueKey();
  final _comment = TextEditingController();
  bool _internal = false;
  bool _busy = false;

  void _reload() => setState(() => _k = UniqueKey());

  Future<void> _send(Map<String, dynamic> allowed) async {
    if (_comment.text.trim().isEmpty) return;
    setState(() => _busy = true);
    final r = await HelpdeskService.ticketComment(TicketCommentRequest(ticketId: widget.ticketId, message: _comment.text.trim(), isInternal: _internal));
    if (!mounted) return;
    setState(() => _busy = false);
    Toast.result(context, r, success: 'Comment added.');
    if (r.ok) {
      _comment.clear();
      _reload();
    }
  }

  Future<void> _status(List<String> moves) async {
    final s = await AppDialogs.choose<String>(context, title: 'Change status', options: [for (final m in moves) MapEntry(m, Fmt.label(m))]);
    if (s == null || !mounted) return;
    final note = await AppDialogs.prompt(context, title: 'Note (optional)', label: 'Note');
    if (note == null || !mounted) return;
    final r = await HelpdeskService.ticketStatus(TicketStatusRequest(ticketId: widget.ticketId, status: s, note: note));
    if (!mounted) return;
    Toast.result(context, r, success: 'Status updated.');
    if (r.ok) _reload();
  }

  Future<void> _assign() async {
    final opts = await Lookups.employees();
    if (!mounted) return;
    final id = await AppDialogs.choose<int>(context, title: 'Assign to', options: [
      const MapEntry<int, String>(-1, 'Unassigned (remove assignee)'),
      for (final o in opts) MapEntry<int, String>(o.value as int, o.label),
    ]);
    if (id == null || !mounted) return; // cancelled
    final r = await HelpdeskService.ticketAssign(widget.ticketId, id == -1 ? null : id);
    if (!mounted) return;
    Toast.result(context, r, success: 'Assignment updated.');
    if (r.ok) _reload();
  }

  @override
  Widget build(BuildContext context) => AppScaffold(
        title: 'Ticket',
        drawer: false,
        body: ApiBuilder(
          key: _k,
          load: () => HelpdeskService.ticketDetail(widget.ticketId),
          builder: (ctx, r, reload) {
            final d = asMap(r.data);
            final t = asMap(d['ticket']);
            final allowed = asMap(d['allowed_actions']);
            final comments = asMapList(d['comments']);
            final moves = (allowed['status_moves'] as List? ?? const []).map((e) => '$e').toList();
            return ListView(padding: const EdgeInsets.all(12), children: [
              InfoCard(
                title: '${t['ticket_code'] ?? ''}  ${t['subject'] ?? ''}',
                trailing: StatusBadge(t['status'] as String?),
                rows: [
                  MapEntry('Description', t['description'] as String?),
                  MapEntry('Category', (t['category'] as Map?)?['name'] as String?),
                  MapEntry('Priority', Fmt.label(t['priority'] as String?)),
                  MapEntry('Raised by', (t['raised_by'] as Map?)?['full_name'] as String?),
                  MapEntry('Assigned to', (t['assigned_to'] as Map?)?['full_name'] as String? ?? 'Unassigned'),
                  MapEntry('Created', Fmt.dateTime(t['created_at'])),
                ],
              ),
              const SizedBox(height: 8),
              Row(children: [
                if (moves.isNotEmpty) Expanded(child: OutlinedButton.icon(onPressed: () => _status(moves), icon: const Icon(Icons.swap_horiz), label: const Text('Change status'))),
                if (moves.isNotEmpty && allowed['assign'] == true) const SizedBox(width: 8),
                if (allowed['assign'] == true) Expanded(child: OutlinedButton.icon(onPressed: _assign, icon: const Icon(Icons.person_add_alt), label: const Text('Assign'))),
              ]),
              const SizedBox(height: 12),
              Text('Conversation', style: Theme.of(context).textTheme.titleMedium),
              for (final c in comments)
                Card(
                  margin: const EdgeInsets.only(top: 8),
                  color: c['is_internal'] == true ? Colors.amber.withValues(alpha: 0.12) : null,
                  child: ListTile(
                    title: Text('${(c['author'] as Map?)?['name'] ?? (c['is_system'] == true ? 'System' : 'Someone')}${c['is_internal'] == true ? '  (internal note)' : ''}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                    subtitle: Text('${c['message']}\n${Fmt.dateTime(c['created_at'])}'),
                  ),
                ),
              if (allowed['comment'] == true) ...[
                const SizedBox(height: 14),
                TextField(controller: _comment, minLines: 2, maxLines: 5, decoration: const InputDecoration(labelText: 'Write a comment')),
                if (allowed['internal_note'] == true)
                  CheckboxListTile(contentPadding: EdgeInsets.zero, value: _internal, onChanged: (v) => setState(() => _internal = v == true), title: const Text('Internal note (hidden from the requester)')),
                PrimaryButton(label: 'Send', busy: _busy, onPressed: () => _send(allowed)),
              ],
            ]);
          },
        ),
      );
}
