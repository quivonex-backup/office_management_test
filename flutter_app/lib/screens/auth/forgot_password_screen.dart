import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../routes/app_routes.dart';
import '../../services/auth_service.dart';
import '../../utils/helpers.dart';
import '../../utils/validators.dart';
import '../../widgets/buttons/primary_button.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/forms/app_text_field.dart';
import 'auth_layout.dart';

/// Port of pages/auth/ForgotPassword.tsx: send OTP -> verify OTP -> new password.
class ForgotPasswordScreen extends StatefulWidget {
  const ForgotPasswordScreen({super.key});
  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  static const _purpose = 'FORGOT_PASSWORD';
  static final _restart = RegExp(r'no otp found|expired|maximum otp attempts', caseSensitive: false);

  final _email = TextEditingController();
  final _otp = TextEditingController();
  final _pw = TextEditingController();
  final _pw2 = TextEditingController();
  int _step = 1;
  bool _busy = false;
  Map<String, String> _errs = {};
  DateTime? _expires;
  DateTime _resendAt = DateTime.fromMillisecondsSinceEpoch(0);
  Timer? _timer;

  @override
  void dispose() {
    _timer?.cancel();
    _email.dispose();
    _otp.dispose();
    _pw.dispose();
    _pw2.dispose();
    super.dispose();
  }

  void _err(String m) => Toast.show(context, m, error: true);

  int get _left => _expires == null ? 0 : _expires!.difference(DateTime.now()).inSeconds.clamp(0, 1 << 30);
  int get _resendIn => _resendAt.difference(DateTime.now()).inSeconds.clamp(0, 1 << 30) + (_resendAt.isAfter(DateTime.now()) ? 1 : 0);

  void _startTimer() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  void _restartFlow(String msg) {
    _timer?.cancel();
    setState(() {
      _step = 1;
      _otp.clear();
      _expires = null;
    });
    _err(msg);
  }

  Future<void> _send() async {
    if (_busy) return;
    final e = Validators.email(_email.text, required: true);
    if (e != null) {
      _err(e);
      return;
    }
    setState(() {
      _busy = true;
      _errs = {};
    });
    final r = await AuthService.sendOtp(_email.text.trim(), _purpose);
    if (!mounted) return;
    setState(() => _busy = false);
    if (!r.ok) {
      setState(() => _errs = r.fieldErrors);
      _err(r.fullMessage);
      return;
    }
    final exp = DateTime.tryParse('${asMap(r.data)['expires_at'] ?? ''}');
    setState(() {
      _expires = exp ?? DateTime.now().add(const Duration(minutes: 5));
      _resendAt = DateTime.now().add(const Duration(seconds: 30));
      _otp.clear();
      _step = 2;
    });
    _startTimer();
    Toast.result(context, r);
  }

  Future<void> _verify() async {
    if (_busy) return;
    if (_otp.text.length != 6) {
      _err('Enter the 6-digit code.');
      return;
    }
    setState(() => _busy = true);
    final r = await AuthService.verifyOtp(_email.text.trim(), _otp.text, _purpose);
    if (!mounted) return;
    setState(() => _busy = false);
    if (r.ok) {
      _timer?.cancel();
      setState(() => _step = 3);
      return;
    }
    if (_restart.hasMatch(r.message)) {
      _restartFlow(r.message);
      return;
    }
    final rem = asMap(r.data)['remaining_attempts'];
    _err(rem != null ? '${r.message} ($rem attempts left)' : r.message);
  }

  Future<void> _reset() async {
    if (_busy) return;
    final pe = Validators.password(_pw.text, 'New password');
    if (pe != null) {
      _err(pe);
      return;
    }
    if (_pw.text != _pw2.text) {
      _err('The two passwords do not match.');
      return;
    }
    setState(() {
      _busy = true;
      _errs = {};
    });
    final r = await AuthService.forgotPassword(_email.text.trim(), _pw.text, _pw2.text);
    if (!mounted) return;
    setState(() => _busy = false);
    if (!r.ok) {
      setState(() => _errs = r.fieldErrors);
      _err(r.fullMessage);
      return;
    }
    // back to Login with the "Password updated" notice (same as React onDone)
    context.read<AuthProvider>().setNotice('Password updated. Please log in.');
    context.canPop() ? context.pop() : context.go(AppRoutes.login);
  }

  @override
  Widget build(BuildContext context) {
    const titles = ['Forgot password', 'Enter the code', 'New password'];
    final lead = _step == 1 ? 'We will email you a one-time code.' : (_step == 2 ? 'Code sent to ${_email.text}.' : 'Choose a new password.');
    final left = _left;
    final resendIn = _resendIn;
    final scheme = Theme.of(context).colorScheme;
    return AuthLayout(
      title: titles[_step - 1],
      lead: lead,
      showBack: true,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          for (var n = 1; n <= 3; n++)
            Expanded(
              child: Container(
                height: 4,
                margin: const EdgeInsets.only(right: 6),
                decoration: BoxDecoration(color: n <= _step ? scheme.primary : scheme.outlineVariant, borderRadius: BorderRadius.circular(2)),
              ),
            ),
        ]),
        const SizedBox(height: 18),
        if (_step == 1) ...[
          AppTextField(label: 'Email', controller: _email, keyboardType: TextInputType.emailAddress, errorText: _errs['email'], onSubmitted: (_) => _send()),
          const SizedBox(height: 14),
          PrimaryButton(label: 'Send code', busy: _busy, onPressed: _send),
        ],
        if (_step == 2) ...[
          AppTextField(
            label: '6-digit code',
            controller: _otp,
            keyboardType: TextInputType.number,
            formatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(6)],
            onSubmitted: (_) => _verify(),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Text(left > 0 ? 'Expires in ${left ~/ 60}:${(left % 60).toString().padLeft(2, '0')}' : 'Code expired. Send a new one.', style: Theme.of(context).textTheme.bodySmall),
          ),
          PrimaryButton(label: 'Verify', busy: _busy, onPressed: left == 0 ? null : _verify),
          const SizedBox(height: 10),
          OutlinedButton(onPressed: (_busy || resendIn > 0) ? null : _send, child: Text(resendIn > 0 ? 'Resend in ${resendIn}s' : 'Resend code')),
        ],
        if (_step == 3) ...[
          AppTextField(label: 'New password', controller: _pw, obscure: true, errorText: _errs['new_password'], autofillHints: const [AutofillHints.newPassword]),
          const SizedBox(height: 14),
          AppTextField(label: 'Confirm password', controller: _pw2, obscure: true, errorText: _errs['confirm_password'], onSubmitted: (_) => _reset()),
          const SizedBox(height: 14),
          PrimaryButton(label: 'Update password', busy: _busy, onPressed: _reset),
        ],
      ]),
    );
  }
}
