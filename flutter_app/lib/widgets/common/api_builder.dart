import 'package:flutter/material.dart';

import '../../api/api_response.dart';
import '../loaders/loading_view.dart';
import 'error_view.dart';

/// Loads data once, shows loading / error (with retry) / the result.
/// The builder receives a `reload` callback to refresh after an action.
class ApiBuilder extends StatefulWidget {
  final Future<ApiResult<dynamic>> Function() load;
  final Widget Function(BuildContext context, ApiResult<dynamic> result, Future<void> Function() reload) builder;
  const ApiBuilder({super.key, required this.load, required this.builder});

  @override
  State<ApiBuilder> createState() => _ApiBuilderState();
}

class _ApiBuilderState extends State<ApiBuilder> {
  ApiResult<dynamic>? _result;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _run();
  }

  Future<void> _run() async {
    if (mounted) setState(() => _loading = _result == null);
    final r = await widget.load();
    if (!mounted) return;
    setState(() {
      _result = r;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading || _result == null) return const LoadingView();
    final r = _result!;
    if (!r.ok) return ErrorView(message: r.fullMessage, onRetry: _run);
    return widget.builder(context, r, _run);
  }
}
