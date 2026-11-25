import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_url.dart';
import '../../constants/app_strings.dart';
import '../../providers/auth_provider.dart';
import '../../utils/helpers.dart';
import 'auth_layout.dart';

/// Several organizations: pick one (React OrgPicker).
class OrgPickerScreen extends StatefulWidget {
  const OrgPickerScreen({super.key});
  @override
  State<OrgPickerScreen> createState() => _OrgPickerScreenState();
}

class _OrgPickerScreenState extends State<OrgPickerScreen> {
  int? _busy;
  String _error = '';

  Future<void> _pick(int id) async {
    setState(() {
      _busy = id;
      _error = '';
    });
    final e = await context.read<AuthProvider>().selectOrganization(id);
    if (!mounted) return;
    setState(() {
      _busy = null;
      if (e != null) _error = e;
    });
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final scheme = Theme.of(context).colorScheme;
    return AuthLayout(
      title: 'Choose an organization',
      lead: 'You belong to more than one. You can switch later from the menu.',
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        if (_error.isNotEmpty)
          Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: scheme.errorContainer, borderRadius: BorderRadius.circular(10)),
            child: Text(_error, style: TextStyle(color: scheme.onErrorContainer)),
          ),
        for (final o in auth.organizations)
          Card(
            margin: const EdgeInsets.only(bottom: 10),
            child: ListTile(
              enabled: _busy == null,
              leading: CircleAvatar(
                backgroundImage: (o.logo ?? '').isNotEmpty ? NetworkImage(ApiUrls.media(o.logo)) : null,
                child: (o.logo ?? '').isEmpty ? Text(Fmt.initials(o.organizationName)) : null,
              ),
              title: Text(o.organizationName, style: const TextStyle(fontWeight: FontWeight.w700)),
              trailing: _busy == o.id ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.chevron_right),
              onTap: () => _pick(o.id),
            ),
          ),
        TextButton(onPressed: auth.logout, child: const Text('Log out')),
      ]),
    );
  }
}

class NoAccessScreen extends StatelessWidget {
  const NoAccessScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return AuthLayout(
      title: AppStrings.noAccessTitle,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: scheme.tertiaryContainer, borderRadius: BorderRadius.circular(10)),
          child: const Text('Your account is not linked to an active organization. Ask the organization owner to add you.'),
        ),
        const SizedBox(height: 14),
        OutlinedButton(onPressed: () => context.read<AuthProvider>().logout(), child: const Text('Log out')),
      ]),
    );
  }
}
