import 'package:flutter/material.dart';

import '../../utils/helpers.dart';

/// Date picker field. The controller holds the API format (yyyy-MM-dd); the user sees it readable.
class DateField extends StatelessWidget {
  final String label;
  final TextEditingController controller;
  final String? Function(String?)? validator;
  final DateTime? firstDate, lastDate;
  final String? errorText;
  const DateField({super.key, required this.label, required this.controller, this.validator, this.firstDate, this.lastDate, this.errorText});

  Future<void> _pick(BuildContext context) async {
    final initial = DateTime.tryParse(controller.text) ?? DateTime.now();
    final d = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: firstDate ?? DateTime(2000),
      lastDate: lastDate ?? DateTime(2100),
    );
    if (d != null) controller.text = Fmt.apiDate(d);
  }

  @override
  Widget build(BuildContext context) => TextFormField(
        controller: controller,
        readOnly: true,
        validator: validator,
        onTap: () => _pick(context),
        decoration: InputDecoration(
          labelText: label,
          errorText: errorText,
          suffixIcon: Row(mainAxisSize: MainAxisSize.min, children: [
            if (controller.text.isNotEmpty) IconButton(icon: const Icon(Icons.clear, size: 18), onPressed: () => controller.clear()),
            const Icon(Icons.calendar_today_outlined, size: 18),
            const SizedBox(width: 12),
          ]),
        ),
      );
}

/// Time picker field. Controller holds HH:mm (24h).
class TimeField extends StatelessWidget {
  final String label;
  final TextEditingController controller;
  final String? Function(String?)? validator;
  final String? errorText;
  const TimeField({super.key, required this.label, required this.controller, this.validator, this.errorText});

  Future<void> _pick(BuildContext context) async {
    final m = RegExp(r'^(\d{1,2}):(\d{2})').firstMatch(controller.text);
    final initial = m == null ? TimeOfDay.now() : TimeOfDay(hour: int.parse(m.group(1)!), minute: int.parse(m.group(2)!));
    final t = await showTimePicker(context: context, initialTime: initial);
    if (t != null) controller.text = Fmt.apiTime(t.hour, t.minute);
  }

  @override
  Widget build(BuildContext context) => TextFormField(
        controller: controller,
        readOnly: true,
        validator: validator,
        onTap: () => _pick(context),
        decoration: InputDecoration(labelText: label, errorText: errorText, suffixIcon: const Icon(Icons.access_time, size: 18)),
      );
}
