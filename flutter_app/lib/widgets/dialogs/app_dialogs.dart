import 'package:flutter/material.dart';

import '../../constants/app_strings.dart';

class AppDialogs {
  AppDialogs._();

  /// Yes/no confirmation. Returns true when confirmed.
  static Future<bool> confirm(BuildContext context, {required String title, required String message, String confirmLabel = AppStrings.confirm, bool danger = false}) async {
    final r = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text(AppStrings.cancel)),
          FilledButton(
            style: FilledButton.styleFrom(
              minimumSize: const Size(90, 40),
              backgroundColor: danger ? Theme.of(ctx).colorScheme.error : null,
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(confirmLabel),
          ),
        ],
      ),
    );
    return r == true;
  }

  /// Asks for a line of text (reason / remarks). Returns null when cancelled.
  static Future<String?> prompt(BuildContext context, {required String title, String label = 'Reason', bool required = false, String confirmLabel = AppStrings.confirm, String initial = ''}) async {
    final c = TextEditingController(text: initial);
    final key = GlobalKey<FormState>();
    final r = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Form(
          key: key,
          child: TextFormField(
            controller: c,
            autofocus: true,
            maxLines: 3,
            minLines: 1,
            decoration: InputDecoration(labelText: label),
            validator: (v) => required && (v ?? '').trim().isEmpty ? '$label is required.' : null,
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text(AppStrings.cancel)),
          FilledButton(
            style: FilledButton.styleFrom(minimumSize: const Size(90, 40)),
            onPressed: () {
              if (key.currentState!.validate()) Navigator.pop(ctx, c.text.trim());
            },
            child: Text(confirmLabel),
          ),
        ],
      ),
    );
    c.dispose();
    return r;
  }

  /// Pick one of several options. Returns the chosen value, or null when cancelled.
  static Future<T?> choose<T>(BuildContext context, {required String title, required List<MapEntry<T, String>> options}) => showDialog<T>(
        context: context,
        builder: (ctx) => SimpleDialog(
          title: Text(title),
          children: [for (final o in options) SimpleDialogOption(onPressed: () => Navigator.pop(ctx, o.key), child: Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: Text(o.value)))],
        ),
      );

  static Future<void> info(BuildContext context, String title, String message) => showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(title: Text(title), content: SingleChildScrollView(child: Text(message)), actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('OK')),
        ]),
      );
}
