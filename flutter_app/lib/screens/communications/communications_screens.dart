import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../constants/app_colors.dart';
import '../../constants/app_constants.dart';
import '../../models/response/notification_response.dart';
import '../../providers/auth_provider.dart';
import '../../services/other_services/business_service.dart';
import '../../services/other_services/communications_service.dart';
import '../../utils/helpers.dart';
import '../../widgets/common/empty_view.dart';
import '../../widgets/common/error_view.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/forms/app_dropdown.dart';
import '../../widgets/forms/opt.dart';
import '../../widgets/loaders/loading_view.dart';
import '../../widgets/navigation/app_scaffold.dart';
import '../generic/crud_list_screen.dart';
import '../generic/crud_models.dart';
import '../generic/lookups.dart';

class AnnouncementsScreen extends StatelessWidget {
  const AnnouncementsScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final manage = context.read<AuthProvider>().can('announcement.manage');
    return CrudListScreen(
      config: CrudConfig(
        title: 'Announcements',
        hasSearch: manage,
        activeFilterKey: manage ? 'is_active' : null,
        list: (f) => manage
            ? CommunicationsService.annList({'search': f['search'], 'priority': f['priority'], if (f['is_active'] == true) 'is_active': true})
            : CommunicationsService.annMy(priority: f['priority'] as String?),
        create: manage ? (b, files) => CommunicationsService.annCreate(b, files: files) : null,
        update: manage ? (i, b, files) => CommunicationsService.annUpdate(i['id'] as int, b, files: files) : null,
        deactivate: manage ? (i) => CommunicationsService.annDeactivate(i['id'] as int) : null,
        managePerms: const ['announcement.manage'],
        filters: [FilterSpec('priority', 'Priority', options: Lookups.strings(AppConstants.announcementPriorities))],
        titleOf: (i) => '${i['is_pinned'] == true ? '📌 ' : ''}${i['title']}',
        subtitleOf: (i) => '${i['description'] ?? ''}\n${Fmt.dateTime(i['created_at'])}',
        badgeOf: (i) => i['priority'] as String?,
        onTap: manage
            ? null
            : (c, i, r) => showDialog<void>(
                  context: c,
                  builder: (ctx) => AlertDialog(
                    title: Text('${i['title']}'),
                    content: SingleChildScrollView(child: Text('${i['description'] ?? ''}')),
                    actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close'))],
                  ),
                ),
        fields: [
          const FieldSpec('title', 'Title', required: true),
          const FieldSpec('description', 'Message', type: FieldType.multiline, required: true),
          FieldSpec('priority', 'Priority', type: FieldType.dropdown, required: true, initial: 'NORMAL', options: Lookups.strings(AppConstants.announcementPriorities)),
          const FieldSpec('is_pinned', 'Pin to top', type: FieldType.boolean),
          const FieldSpec('expires_at', 'Expires on', type: FieldType.date),
          const FieldSpec('attachments', 'Attachment', type: FieldType.file),
        ],
      ),
    );
  }
}

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});
  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  final List<AppNotification> _items = [];
  bool _loading = true, _hasMore = false, _unreadOnly = false;
  String? _error;
  int _unread = 0;

  @override
  void initState() {
    super.initState();
    _load(reset: true);
  }

  Future<void> _load({bool reset = false}) async {
    if (reset) setState(() => _loading = true);
    final r = await CommunicationsService.notifList(
        unreadOnly: _unreadOnly ? true : null, limit: 25, beforeId: reset || _items.isEmpty ? null : _items.last.id);
    if (!mounted) return;
    setState(() {
      _loading = false;
      if (!r.ok) {
        _error = r.fullMessage;
        return;
      }
      _error = null;
      final page = NotificationPage.fromJson(asMap(r.data));
      if (reset) _items.clear();
      _items.addAll(page.notifications);
      _hasMore = page.hasMore;
      _unread = page.unreadCount;
    });
  }

  Future<void> _read(AppNotification n) async {
    if (n.isRead) return;
    final r = await CommunicationsService.notifRead([n.id]);
    if (r.ok) _load(reset: true);
  }

  Future<void> _readAll() async {
    final r = await CommunicationsService.notifReadAll();
    if (!mounted) return;
    Toast.result(context, r, success: 'All marked as read.');
    _load(reset: true);
  }

  Future<void> _delete(AppNotification n) async {
    final r = await CommunicationsService.notifDelete([n.id]);
    if (!mounted) return;
    if (r.ok) {
      setState(() => _items.removeWhere((x) => x.id == n.id));
    } else {
      Toast.result(context, r);
    }
  }

  @override
  Widget build(BuildContext context) => AppScaffold(
        title: 'Notifications${_unread > 0 ? ' ($_unread)' : ''}',
        actions: [
          IconButton(
            tooltip: _unreadOnly ? 'Show all' : 'Unread only',
            icon: Icon(_unreadOnly ? Icons.mark_email_unread : Icons.mark_email_unread_outlined),
            onPressed: () {
              setState(() => _unreadOnly = !_unreadOnly);
              _load(reset: true);
            },
          ),
          IconButton(tooltip: 'Mark all read', icon: const Icon(Icons.done_all), onPressed: _readAll),
        ],
        body: _loading
            ? const LoadingView()
            : _error != null
                ? ErrorView(message: _error!, onRetry: () => _load(reset: true))
                : _items.isEmpty
                    ? const EmptyView(message: 'No notifications.', icon: Icons.notifications_none)
                    : RefreshIndicator(
                        onRefresh: () => _load(reset: true),
                        child: ListView.builder(
                          itemCount: _items.length + (_hasMore ? 1 : 0),
                          itemBuilder: (_, i) {
                            if (i == _items.length) {
                              return Padding(padding: const EdgeInsets.all(12), child: OutlinedButton(onPressed: _load, child: const Text('Load more')));
                            }
                            final n = _items[i];
                            return Dismissible(
                              key: ValueKey('n${n.id}'),
                              background: Container(color: AppColors.danger, alignment: Alignment.centerRight, padding: const EdgeInsets.only(right: 20), child: const Icon(Icons.delete, color: Colors.white)),
                              direction: DismissDirection.endToStart,
                              onDismissed: (_) => _delete(n),
                              child: ListTile(
                                tileColor: n.isRead ? null : Theme.of(context).colorScheme.primary.withValues(alpha: 0.06),
                                leading: Icon(n.priority == 'HIGH' ? Icons.priority_high : Icons.notifications_outlined, color: n.priority == 'HIGH' ? AppColors.danger : null),
                                title: Text(n.title, style: TextStyle(fontWeight: n.isRead ? FontWeight.w400 : FontWeight.w700)),
                                subtitle: Text('${n.body}\n${Fmt.dateTime(n.createdAt)}'),
                                isThreeLine: true,
                                onTap: () => _read(n),
                              ),
                            );
                          },
                        ),
                      ),
      );
}

/// Project chat: pick a project, read messages (polls every 10 s), send text.
class ProjectChatScreen extends StatefulWidget {
  const ProjectChatScreen({super.key});
  @override
  State<ProjectChatScreen> createState() => _ProjectChatScreenState();
}

class _ProjectChatScreenState extends State<ProjectChatScreen> {
  List<Opt> _projects = [];
  bool _loadingProjects = true;
  int? _projectId;
  final List<Map<String, dynamic>> _messages = [];
  bool _canPost = false, _loadingChat = false;
  String? _error;
  final _input = TextEditingController();
  final _scroll = ScrollController();
  Timer? _timer;
  bool _sending = false;

  @override
  void initState() {
    super.initState();
    _loadProjects();
  }

  @override
  void dispose() {
    _timer?.cancel();
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _loadProjects() async {
    final auth = context.read<AuthProvider>();
    List<Opt> opts;
    if (auth.can('project.manage')) {
      opts = await Lookups.projects();
    } else {
      final r = await BusinessService.myProjects();
      opts = [for (final p in asMapList(asMap(r.data)['projects'])) Opt(p['project_id'], '${p['project_name']}')];
    }
    if (!mounted) return;
    setState(() {
      _projects = opts;
      _loadingProjects = false;
    });
  }

  Future<void> _open(int? id) async {
    _timer?.cancel();
    setState(() {
      _projectId = id;
      _messages.clear();
      _error = null;
      _loadingChat = id != null;
    });
    if (id == null) return;
    await _fetch(initial: true);
    _timer = Timer.periodic(const Duration(seconds: 10), (_) => _fetch());
  }

  Future<void> _fetch({bool initial = false}) async {
    final id = _projectId;
    if (id == null) return;
    final last = _messages.isEmpty ? null : _messages.last['id'] as int;
    final r = await CommunicationsService.chatMessages(id, sinceId: initial ? null : last, limit: initial ? 50 : null);
    if (!mounted || id != _projectId) return;
    setState(() {
      _loadingChat = false;
      if (!r.ok) {
        _error = r.fullMessage;
        return;
      }
      _error = null;
      final d = asMap(r.data);
      _canPost = d['can_current_user_post'] == true;
      final incoming = asMapList(d['messages']);
      if (initial) _messages.clear();
      final known = _messages.map((m) => m['id']).toSet();
      _messages.addAll(incoming.where((m) => !known.contains(m['id'])));
      _messages.sort((a, b) => (a['id'] as int).compareTo(b['id'] as int));
    });
    if (_scroll.hasClients) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _scroll.jumpTo(_scroll.position.maxScrollExtent));
    }
  }

  Future<void> _send() async {
    final text = _input.text.trim();
    if (text.isEmpty || _projectId == null) return;
    setState(() => _sending = true);
    final r = await CommunicationsService.chatSend(_projectId!, text);
    if (!mounted) return;
    setState(() => _sending = false);
    if (r.ok) {
      _input.clear();
      _fetch();
    } else {
      Toast.result(context, r);
    }
  }

  @override
  Widget build(BuildContext context) => AppScaffold(
        title: 'Project chat',
        body: _loadingProjects
            ? const LoadingView()
            : Column(children: [
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: AppDropdown(label: 'Project', value: _projectId, items: _projects, allowClear: false, onChanged: (v) => _open(v as int?)),
                ),
                Expanded(
                  child: _projectId == null
                      ? const EmptyView(message: 'Choose a project to open its chat.', icon: Icons.forum_outlined)
                      : _loadingChat
                          ? const LoadingView()
                          : _error != null
                              ? ErrorView(message: _error!, onRetry: () => _fetch(initial: true))
                              : _messages.isEmpty
                                  ? const EmptyView(message: 'No messages yet.', icon: Icons.chat_bubble_outline)
                                  : ListView.builder(
                                      controller: _scroll,
                                      padding: const EdgeInsets.all(12),
                                      itemCount: _messages.length,
                                      itemBuilder: (_, i) {
                                        final m = _messages[i];
                                        final s = asMap(m['sender']);
                                        final deleted = m['is_deleted'] == true;
                                        return Card(
                                          margin: const EdgeInsets.only(bottom: 8),
                                          child: ListTile(
                                            dense: true,
                                            title: Text('${s['name'] ?? ''}  ·  ${s['role_label'] ?? ''}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12.5)),
                                            subtitle: Text(deleted ? 'This message was deleted.' : '${m['body']}\n${Fmt.dateTime(m['created_at'])}'),
                                          ),
                                        );
                                      },
                                    ),
                ),
                if (_projectId != null && _canPost)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
                    child: Row(children: [
                      Expanded(child: TextField(controller: _input, minLines: 1, maxLines: 4, decoration: const InputDecoration(hintText: 'Write a message', isDense: true))),
                      const SizedBox(width: 8),
                      IconButton.filled(onPressed: _sending ? null : _send, icon: const Icon(Icons.send)),
                    ]),
                  ),
              ]),
      );
}
