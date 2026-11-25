import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../services/auth_service.dart';
import '../../widgets/buttons/primary_button.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/forms/app_text_field.dart';
import '../../widgets/navigation/app_scaffold.dart';

/// Port of pages/settings/ChangePassword.tsx. Logs out afterwards so the old session does not stay open.
class ChangePasswordScreen extends StatefulWidget {
  const ChangePasswordScreen({super.key});
  @override
  State<ChangePasswordScreen> createState() => _ChangePasswordScreenState();
}

class _ChangePasswordScreenState extends State<ChangePasswordScreen> {
  final _o = TextEditingController();
  final _n = TextEditingController();
  final _c = TextEditingController();
  bool _busy = false;
  Map<String, String> _errs = {};

  @override
  void initState() {
    super.initState();
    for (final c in [_o, _n, _c]) {
      c.addListener(() => setState(() {}));
    }
  }

  @override
  void dispose() {
    _o.dispose();
    _n.dispose();
    _c.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final o = _o.text, n = _n.text, c = _c.text;
    final e = <String, String>{};
    if (o.isEmpty) e['old_password'] = 'Enter your current password.';
    if (n.length < 8) {
      e['new_password'] = 'New password must be at least 8 characters.';
    } else if (n == o) {
      e['new_password'] = 'New password must be different.';
    }
    if (n != c) e['confirm_password'] = 'The two passwords do not match.';
    setState(() => _errs = e);
    if (e.isNotEmpty) return;
    setState(() => _busy = true);
    final r = await AuthService.changePassword(o, n, c);
    if (!mounted) return;
    setState(() => _busy = false);
    if (!r.ok) {
      setState(() => _errs = r.fieldErrors);
      Toast.show(context, r.fullMessage, error: true);
      return;
    }
    Toast.result(context, r);
    final auth = context.read<AuthProvider>();
    await auth.logout();
  }

  @override
  Widget build(BuildContext context) {
    final n = _n.text;
    final rules = <MapEntry<String, bool>>[
      MapEntry('At least 8 characters', n.length >= 8),
      MapEntry('Letters and numbers', RegExp(r'[A-Za-z]').hasMatch(n) && RegExp(r'\d').hasMatch(n)),
      MapEntry('Both new passwords match', n.isNotEmpty && n == _c.text),
      MapEntry('Different from the current password', n.isNotEmpty && n != _o.text),
    ];
    final scheme = Theme.of(context).colorScheme;
    return AppScaffold(
      title: 'Change password',
      body: ListView(padding: const EdgeInsets.all(14), children: [
        Text('You will be logged out afterwards and can log in with the new one.', style: Theme.of(context).textTheme.bodyMedium),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('A strong password', style: TextStyle(fontWeight: FontWeight.w700)),
              for (final r in rules)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Row(children: [
                    Icon(r.value ? Icons.check_circle : Icons.radio_button_unchecked, size: 18, color: r.value ? Colors.green : scheme.outline),
                    const SizedBox(width: 8),
                    Text(r.key),
                  ]),
                ),
            ]),
          ),
        ),
        const SizedBox(height: 12),
        AppTextField(label: 'Current password', controller: _o, obscure: true, errorText: _errs['old_password'], autofillHints: const [AutofillHints.password]),
        const SizedBox(height: 12),
        AppTextField(label: 'New password', controller: _n, obscure: true, errorText: _errs['new_password'], autofillHints: const [AutofillHints.newPassword]),
        const SizedBox(height: 12),
        AppTextField(label: 'Confirm new password', controller: _c, obscure: true, errorText: _errs['confirm_password'], onSubmitted: (_) => _save()),
        const SizedBox(height: 16),
        PrimaryButton(label: 'Update password', busy: _busy, onPressed: _save),
      ]),
    );
  }
}
