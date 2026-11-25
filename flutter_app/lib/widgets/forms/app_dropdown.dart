import 'package:flutter/material.dart';

import 'opt.dart';

class AppDropdown extends StatelessWidget {
  final String label;
  final dynamic value;
  final List<Opt> items;
  final void Function(dynamic) onChanged;
  final String? Function(dynamic)? validator;
  final bool allowClear;
  final String? errorText;

  const AppDropdown({
    super.key,
    required this.label,
    required this.value,
    required this.items,
    required this.onChanged,
    this.validator,
    this.allowClear = true,
    this.errorText,
  });

  @override
  Widget build(BuildContext context) {
    final has = items.any((o) => o.value == value);
    return DropdownButtonFormField<dynamic>(
      value: has ? value : null,
      isExpanded: true,
      validator: validator,
      decoration: InputDecoration(
        labelText: label,
        errorText: errorText,
        suffixIcon: allowClear && has
            ? IconButton(icon: const Icon(Icons.clear, size: 18), onPressed: () => onChanged(null))
            : null,
      ),
      items: [for (final o in items) DropdownMenuItem<dynamic>(value: o.value, child: Text(o.label, overflow: TextOverflow.ellipsis))],
      onChanged: onChanged,
    );
  }
}
