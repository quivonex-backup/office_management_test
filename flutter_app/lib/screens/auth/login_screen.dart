import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../../constants/app_colors.dart';
import '../../constants/app_strings.dart';
import '../../providers/auth_provider.dart';
import '../../routes/app_routes.dart';
import '../../services/storage_service.dart';
import '../../utils/validators.dart';
import '../../widgets/buttons/primary_button.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/forms/app_text_field.dart';
import 'auth_layout.dart';

/// Port of pages/auth/Login.tsx. One field `username` holds a username OR an email.
/// Remember me (on by default) keeps the login and prefills the username; the password is never stored.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _form = GlobalKey<FormState>();
  final _user = TextEditingController();
  final _pass = TextEditingController();
  bool _remember = true;
  bool _busy = false;
  Map<String, String> _errs = {};

  @override
  void initState() {
    super.initState();
    _loadRemembered();
  }

  Future<void> _loadRemembered() async {
    final s = StorageService.instance;
    final u = await s.getString(StorageService.kRememberUser);
    final off = await s.getString(StorageService.kRememberOff);
    if (!mounted) return;
    setState(() {
      _user.text = u ?? '';
      _remember = u != null || off == null;
    });
  }

  @override
  void dispose() {
    _user.dispose();
    _pass.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_busy) return;
    final auth = context.read<AuthProvider>();
    auth.clearNotice();
    setState(() => _errs = {});
    if (!_form.currentState!.validate()) return;
    setState(() => _busy = true);
    final r = await auth.login(_user.text.trim(), _pass.text, _remember);
    final s = StorageService.instance;
    if (r.ok && _remember) {
      await s.setString(StorageService.kRememberUser, _user.text.trim());
      await s.remove(StorageService.kRememberOff);
    } else if (r.ok) {
      await s.remove(StorageService.kRememberUser);
      await s.setString(StorageService.kRememberOff, '1');
    }
    if (!mounted) return;
    if (!r.ok) {
      setState(() => _errs = r.fieldErrors);
      Toast.result(context, r);
    }
    setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final notice = context.select<AuthProvider, String?>((a) => a.notice);
    return AuthLayout(
      title: AppStrings.signIn,
      lead: AppStrings.signInLead,
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          if (notice != null)
            Container(
              margin: const EdgeInsets.only(bottom: 14),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: AppColors.success.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(10)),
              child: Text(notice),
            ),
          AppTextField(
            label: 'Username or email',
            controller: _user,
            prefixIcon: Icons.person_outline,
            validator: Validators.loginId,
            errorText: _errs['username'],
            textInputAction: TextInputAction.next,
            autofillHints: const [AutofillHints.username],
          ),
          const SizedBox(height: 14),
          AppTextField(
            label: 'Password',
            controller: _pass,
            obscure: true,
            prefixIcon: Icons.lock_outline,
            validator: (v) => (v == null || v.isEmpty) ? 'Enter your password.' : null,
            errorText: _errs['password'],
            onSubmitted: (_) => _submit(),
            textInputAction: TextInputAction.done,
            autofillHints: const [AutofillHints.password],
          ),
          const SizedBox(height: 6),
          Row(children: [
            Expanded(
              child: InkWell(
                onTap: () => setState(() => _remember = !_remember),
                child: Row(children: [
                  Checkbox(value: _remember, onChanged: (v) => setState(() => _remember = v ?? true)),
                  const Text('Remember me'),
                ]),
              ),
            ),
            TextButton(
              onPressed: () => context.push(AppRoutes.forgotPassword),
              child: const Text('Forgot password?'),
            ),
          ]),
          const SizedBox(height: 8),
          PrimaryButton(label: AppStrings.signIn, busy: _busy, onPressed: _submit),
        ]),
      ),
    );
  }
}
