import 'package:flutter/material.dart';

import '../../api/api_request.dart';
import '../../models/response/report_response.dart';
import '../../services/other_services/reports_service.dart';
import '../../utils/helpers.dart';
import '../../widgets/buttons/primary_button.dart';
import '../../widgets/common/api_builder.dart';
import '../../widgets/common/empty_view.dart';
import '../../widgets/common/error_view.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/forms/app_dropdown.dart';
import '../../widgets/forms/app_text_field.dart';
import '../../widgets/forms/date_field.dart';
import '../../widgets/forms/opt.dart';
import '../../widgets/loaders/loading_view.dart';
import '../../widgets/navigation/app_scaffold.dart';
import '../../widgets/tables/pagination_bar.dart';
import '../../widgets/tables/report_table.dart';
import '../generic/lookups.dart';

class ReportHubScreen extends StatelessWidget {
  const ReportHubScreen({super.key});
  @override
  Widget build(BuildContext context) => AppScaffold(
        title: 'Reports',
        body: ApiBuilder(
          load: ReportsService.reportList,
          builder: (ctx, r, reload) {
            final reports = asMapList(asMap(r.data)['reports']).map(ReportMeta.fromJson).toList();
            if (reports.isEmpty) return const EmptyView(message: 'No reports are available for you.', icon: Icons.bar_chart_outlined);
            final groups = <String, List<ReportMeta>>{};
            for (final m in reports) {
              groups.putIfAbsent(m.group, () => []).add(m);
            }
            return RefreshIndicator(
              onRefresh: reload,
              child: ListView(padding: const EdgeInsets.all(12), children: [
                for (final g in groups.entries) ...[
                  Padding(padding: const EdgeInsets.fromLTRB(4, 12, 4, 6), child: Text(g.key, style: Theme.of(context).textTheme.titleMedium)),
                  for (final m in g.value)
                    Card(
                      margin: const EdgeInsets.only(bottom: 8),
                      child: ListTile(
                        leading: const Icon(Icons.insert_chart_outlined),
                        title: Text(m.title),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => ReportRunScreen(meta: m))),
                      ),
                    ),
                ],
              ]),
            );
          },
        ),
      );
}

/// One screen for every report. Filters, columns, rows and totals all come from the server.
class ReportRunScreen extends StatefulWidget {
  final ReportMeta meta;
  const ReportRunScreen({super.key, required this.meta});
  @override
  State<ReportRunScreen> createState() => _ReportRunScreenState();
}

class _ReportRunScreenState extends State<ReportRunScreen> {
  final Map<String, dynamic> _filters = {};
  final Map<String, TextEditingController> _text = {};
  final Map<String, Future<List<Opt>>> _optFutures = {};
  ReportData? _data;
  bool _loading = false, _showFilters = true;
  String? _error;
  int _page = 1;
  int _size = 50; // same default as the React report page

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    for (final f in widget.meta.filters) {
      if (f.type == 'date') {
        final d = f.key == 'from_date' ? DateTime(now.year, now.month, 1) : DateTime(now.year, now.month + 1, 0);
        _text[f.key] = TextEditingController(text: Fmt.apiDate(d));
      } else if (f.type == 'text' || f.type == 'month') {
        _text[f.key] = TextEditingController(text: f.type == 'month' ? '${now.year}-${now.month.toString().padLeft(2, '0')}' : '');
      } else if (f.type == 'choice' && f.defaultValue != null && f.options.any((o) => o.key == f.defaultValue)) {
        _filters[f.key] = f.defaultValue;
      }
    }
    _run();
  }

  @override
  void dispose() {
    for (final c in _text.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<List<Opt>> _lookup(String type) => _optFutures.putIfAbsent(type, () {
        switch (type) {
          case 'employee':
            return Lookups.employees();
          case 'department':
            return Lookups.departments();
          case 'designation':
            return Lookups.designations();
          case 'branch':
            return Lookups.branches();
          case 'access_role':
            return Lookups.accessRoles();
          case 'leave_type':
            return Lookups.leaveTypes();
          case 'client':
            return Lookups.clients();
          case 'project':
            return Lookups.projects();
          case 'vendor':
            return Lookups.vendors();
          case 'ticket_category':
            return Lookups.ticketCategories();
          default:
            return Future.value(<Opt>[]);
        }
      });

  Map<String, dynamic> _body() {
    final b = <String, dynamic>{};
    for (final f in widget.meta.filters) {
      dynamic v;
      if (_text.containsKey(f.key)) {
        v = _text[f.key]!.text.trim();
      } else {
        v = _filters[f.key];
      }
      if (v == null || v == false || (v is String && v.isEmpty)) continue;
      b[f.key] = (v is String && f.key.endsWith('_id') && int.tryParse(v) != null) ? int.parse(v) : v;
    }
    return b;
  }

  Future<void> _run({int page = 1}) async {
    setState(() {
      _loading = true;
      _page = page;
      _error = null;
    });
    final r = await ReportsService.run(widget.meta.key, ReportRunRequest(filters: _body(), page: page, pageSize: _size).toJson());
    if (!mounted) return;
    setState(() {
      _loading = false;
      if (r.ok) {
        _data = ReportData.fromJson(asMap(r.data));
      } else {
        _error = r.fullMessage;
      }
    });
  }

  Future<void> _excel() async {
    final r = await ReportsService.excel(widget.meta.key, _body());
    if (!mounted) return;
    if (!r.ok) {
      Toast.show(context, r.fullMessage, error: true);
      return;
    }
    final err = await saveAndOpen(r.data!);
    if (err != null && mounted) Toast.show(context, err, error: true);
  }

  Widget _filter(ReportFilter f) {
    final label = Fmt.label(f.key.replaceAll(RegExp(r'_id$'), ''));
    switch (f.type) {
      case 'date':
        return DateField(label: label, controller: _text[f.key]!);
      case 'bool':
        return SwitchListTile(contentPadding: EdgeInsets.zero, title: Text(label), value: _filters[f.key] == true, onChanged: (v) => setState(() => _filters[f.key] = v));
      case 'month':
        return AppTextField(label: '$label (yyyy-mm)', controller: _text[f.key]!);
      case 'choice':
        return AppDropdown(
          label: label,
          value: _filters[f.key],
          allowClear: f.key != 'view',
          items: [for (final o in f.options) Opt(o.key, o.value)],
          onChanged: (v) => setState(() => _filters[f.key] = v),
        );
      case 'text':
        return AppTextField(label: label, controller: _text[f.key]!);
      default:
        return FutureBuilder<List<Opt>>(
          future: _lookup(f.type),
          builder: (_, s) => AppDropdown(
            label: label,
            value: _filters[f.key],
            items: s.data ?? const [],
            onChanged: (v) => setState(() => _filters[f.key] = v),
          ),
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _data;
    return AppScaffold(
      title: widget.meta.title,
      drawer: false,
      actions: [
        IconButton(icon: Icon(_showFilters ? Icons.filter_alt : Icons.filter_alt_outlined), onPressed: () => setState(() => _showFilters = !_showFilters)),
        if (widget.meta.formats.contains('xlsx')) IconButton(icon: const Icon(Icons.table_view_outlined), tooltip: 'Export Excel', onPressed: _excel),
      ],
      body: Column(children: [
        if (_showFilters && widget.meta.filters.isNotEmpty)
          ExpansionTile(
            initiallyExpanded: true,
            title: const Text('Filters'),
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(14, 0, 14, 12),
                child: Column(children: [
                  for (final f in widget.meta.filters) Padding(padding: const EdgeInsets.only(bottom: 10), child: _filter(f)),
                  PrimaryButton(label: 'Run report', icon: Icons.play_arrow, onPressed: () => _run()),
                ]),
              ),
            ],
          ),
        Expanded(
          child: _loading
              ? const LoadingView()
              : _error != null
                  ? ErrorView(message: _error!, onRetry: () => _run(page: _page))
                  : d == null || d.rows.isEmpty
                      ? const EmptyView(message: 'No rows for these filters.')
                      : ListView(children: [
                          if (d.summary.isNotEmpty)
                            Padding(
                              padding: const EdgeInsets.all(12),
                              child: Wrap(spacing: 8, runSpacing: 8, children: [
                                for (final e in d.summary.entries)
                                  if (e.value is num || e.value is String)
                                    Chip(label: Text('${Fmt.label(e.key)}: ${e.value is num ? Fmt.number(e.value) : e.value}')),
                              ]),
                            ),
                          ReportTable(columns: d.columns, rows: d.rows, totals: d.totals),
                          PaginationBar(page: d.page, totalPages: d.totalPages, totalRows: d.totalRows, onPage: (p) => _run(page: p), pageSize: _size, onPageSize: (n) { _size = n; _run(page: 1); }),
                        ]),
        ),
      ]),
    );
  }
}
