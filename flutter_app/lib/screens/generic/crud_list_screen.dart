import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../utils/helpers.dart';
import '../../widgets/common/empty_view.dart';
import '../../widgets/common/error_view.dart';
import '../../widgets/common/status_badge.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/dialogs/app_dialogs.dart';
import '../../widgets/forms/opt.dart';
import '../../widgets/loaders/loading_view.dart';
import '../../widgets/navigation/app_scaffold.dart';
import '../../api/api_response.dart';
import 'crud_form_screen.dart';
import 'crud_models.dart';

/// One screen for any list module: search, filters, pull to refresh, add / edit / deactivate,
/// permission-aware actions, loading / empty / error states. Driven by a [CrudConfig].
class CrudListScreen extends StatefulWidget {
  final CrudConfig config;
  final bool drawer;
  const CrudListScreen({super.key, required this.config, this.drawer = true});

  @override
  State<CrudListScreen> createState() => _CrudListScreenState();
}

class _CrudListScreenState extends State<CrudListScreen> {
  final _search = TextEditingController();
  Timer? _debounce;
  final Map<String, dynamic> _filterValues = {};
  final Map<String, List<Opt>> _filterOpts = {};
  bool _showInactive = false;
  bool _loading = true;
  ApiResult<dynamic>? _result;
  List<Item> _items = [];

  CrudConfig get c => widget.config;

  @override
  void initState() {
    super.initState();
    for (final f in c.filters) {
      if (f.options != null) _filterOpts[f.key] = f.options!;
      if (f.loadOptions != null) {
        f.loadOptions!().then((o) {
          if (mounted) setState(() => _filterOpts[f.key] = o);
        });
      }
    }
    _load();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _search.dispose();
    super.dispose();
  }

  Map<String, dynamic> _buildFilters() {
    final m = <String, dynamic>{...c.baseFilters};
    if (c.hasSearch && _search.text.trim().isNotEmpty) m['search'] = _search.text.trim();
    _filterValues.forEach((k, v) {
      if (v != null && v.toString().isNotEmpty) m[k] = v;
    });
    if (c.activeFilterKey == 'is_active' && !_showInactive) m['is_active'] = true;
    if (c.activeFilterKey == 'include_inactive' && _showInactive) m['include_inactive'] = true;
    return m;
  }

  Future<void> _load() async {
    if (mounted) setState(() => _loading = _result == null);
    final r = await c.list(_buildFilters());
    if (!mounted) return;
    setState(() {
      _result = r;
      _items = r.ok ? asMapList(r.data) : [];
      _loading = false;
    });
  }

  bool _canManage(AuthProvider a) => a.canAny(c.managePerms);

  Future<void> _openForm([Item? item]) async {
    final saved = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => CrudFormScreen(
          title: item == null ? '${c.createLabel} ${c.title.toLowerCase()}'.trim() : 'Edit',
          fields: c.fields,
          item: item,
          onSubmit: (body, files) => item == null ? c.create!(body, files) : c.update!(item, body, files),
        ),
      ),
    );
    if (saved == true) _load();
  }

  Future<void> _deactivate(Item item) async {
    final ok = await AppDialogs.confirm(
      context,
      title: '${c.deactivateLabel}?',
      message: '${c.titleOf(item)}\n\n${c.deactivateWarning}',
      confirmLabel: c.deactivateLabel,
      danger: true,
    );
    if (!ok || !mounted) return;
    final r = await c.deactivate!(item);
    if (!mounted) return;
    Toast.result(context, r, success: 'Done.');
    if (r.ok) _load();
  }

  bool _isActive(Item i) => i['is_active'] != false;

  Widget _tile(Item item, AuthProvider auth) {
    final canManage = _canManage(auth);
    final active = _isActive(item);
    final badge = c.badgeOf?.call(item);
    final actions = c.rowActions.where((a) => a.visible == null || a.visible!(item)).toList();
    final hasMenu = (canManage && c.deactivate != null && active) || actions.isNotEmpty;
    final tapEdit = canManage && c.update != null && c.fields.isNotEmpty;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Opacity(
        opacity: active ? 1 : 0.55,
        child: ListTile(
          onTap: c.onTap != null ? () => c.onTap!(context, item, _load) : (tapEdit ? () => _openForm(item) : null),
          title: Text(c.titleOf(item), style: const TextStyle(fontWeight: FontWeight.w600)),
          subtitle: c.subtitleOf?.call(item) == null ? null : Text(c.subtitleOf!(item)!, maxLines: 3, overflow: TextOverflow.ellipsis),
          trailing: Row(mainAxisSize: MainAxisSize.min, children: [
            if (!active) const StatusBadge('INACTIVE') else if (badge != null) StatusBadge(badge),
            if (c.trailingOf?.call(item) != null)
              Padding(padding: const EdgeInsets.only(left: 8), child: Text(c.trailingOf!(item)!, style: const TextStyle(fontWeight: FontWeight.w600))),
            if (hasMenu)
              PopupMenuButton<int>(
                onSelected: (i) async {
                  if (i == -1) {
                    _deactivate(item);
                  } else {
                    final reload = await actions[i].run(context, item);
                    if (reload) _load();
                  }
                },
                itemBuilder: (_) => [
                  for (var i = 0; i < actions.length; i++)
                    PopupMenuItem(value: i, child: Row(children: [Icon(actions[i].icon, size: 18), const SizedBox(width: 10), Text(actions[i].label)])),
                  if (canManage && c.deactivate != null && active)
                    PopupMenuItem(value: -1, child: Row(children: [const Icon(Icons.block, size: 18), const SizedBox(width: 10), Text(c.deactivateLabel)])),
                ],
              ),
          ]),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final canCreate = c.create != null && c.fields.isNotEmpty && _canManage(auth);
    return AppScaffold(
      title: c.title,
      drawer: widget.drawer,
      actions: [IconButton(icon: const Icon(Icons.refresh), onPressed: _load)],
      floatingActionButton: canCreate ? FloatingActionButton.extended(onPressed: () => _openForm(), icon: const Icon(Icons.add), label: Text(c.createLabel)) : null,
      body: Column(children: [
        if (c.hasSearch || c.filters.isNotEmpty || c.activeFilterKey != null)
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 4),
            child: Column(children: [
              if (c.hasSearch)
                TextField(
                  controller: _search,
                  onChanged: (_) {
                    _debounce?.cancel();
                    _debounce = Timer(const Duration(milliseconds: 450), _load);
                  },
                  decoration: InputDecoration(
                    hintText: 'Search',
                    prefixIcon: const Icon(Icons.search),
                    isDense: true,
                    suffixIcon: _search.text.isEmpty ? null : IconButton(icon: const Icon(Icons.clear), onPressed: () { _search.clear(); _load(); }),
                  ),
                ),
              if (c.filters.isNotEmpty)
                SizedBox(
                  height: 56,
                  child: ListView(scrollDirection: Axis.horizontal, children: [
                    for (final f in c.filters)
                      Padding(
                        padding: const EdgeInsets.only(right: 8, top: 8),
                        child: SizedBox(
                          width: 170,
                          child: DropdownButtonFormField<dynamic>(
                            value: (_filterOpts[f.key] ?? const []).any((o) => o.value == _filterValues[f.key]) ? _filterValues[f.key] : null,
                            isExpanded: true,
                            decoration: InputDecoration(labelText: f.label, isDense: true, contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10)),
                            items: [
                              const DropdownMenuItem<dynamic>(value: null, child: Text('All')),
                              for (final o in _filterOpts[f.key] ?? const <Opt>[]) DropdownMenuItem<dynamic>(value: o.value, child: Text(o.label, overflow: TextOverflow.ellipsis)),
                            ],
                            onChanged: (v) {
                              setState(() => _filterValues[f.key] = v);
                              _load();
                            },
                          ),
                        ),
                      ),
                  ]),
                ),
              if (c.activeFilterKey != null)
                Align(
                  alignment: Alignment.centerRight,
                  child: Row(mainAxisSize: MainAxisSize.min, children: [
                    const Text('Show inactive'),
                    Switch(value: _showInactive, onChanged: (v) { setState(() => _showInactive = v); _load(); }),
                  ]),
                ),
            ]),
          ),
        if (c.header != null && _result != null && _result!.ok) c.header!(context, _result!),
        Expanded(child: _body(auth)),
      ]),
    );
  }

  Widget _body(AuthProvider auth) {
    if (_loading) return const LoadingView();
    if (_result != null && !_result!.ok) return ErrorView(message: _result!.fullMessage, onRetry: _load);
    if (_items.isEmpty) return RefreshIndicator(onRefresh: _load, child: ListView(children: [SizedBox(height: 320, child: EmptyView(message: c.emptyMessage))]));
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 90),
        itemCount: _items.length,
        itemBuilder: (_, i) => _tile(_items[i], auth),
      ),
    );
  }
}
