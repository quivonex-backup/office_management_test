import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class AppTextField extends StatefulWidget {
  final String label;
  final TextEditingController controller;
  final String? Function(String?)? validator;
  final TextInputType? keyboardType;
  final bool obscure;
  final int maxLines;
  final IconData? prefixIcon;
  final String? hint;
  final String? errorText;
  final bool readOnly;
  final List<TextInputFormatter>? formatters;
  final void Function(String)? onSubmitted;
  final TextInputAction? textInputAction;
  final Iterable<String>? autofillHints;

  const AppTextField({
    super.key,
    required this.label,
    required this.controller,
    this.validator,
    this.keyboardType,
    this.obscure = false,
    this.maxLines = 1,
    this.prefixIcon,
    this.hint,
    this.errorText,
    this.readOnly = false,
    this.formatters,
    this.onSubmitted,
    this.textInputAction,
    this.autofillHints,
  });

  @override
  State<AppTextField> createState() => _AppTextFieldState();
}

class _AppTextFieldState extends State<AppTextField> {
  late bool _hidden = widget.obscure;

  @override
  Widget build(BuildContext context) {
    return TextFormField(
      controller: widget.controller,
      validator: widget.validator,
      keyboardType: widget.keyboardType,
      obscureText: _hidden,
      maxLines: widget.obscure ? 1 : widget.maxLines,
      readOnly: widget.readOnly,
      inputFormatters: widget.formatters,
      onFieldSubmitted: widget.onSubmitted,
      textInputAction: widget.textInputAction,
      autofillHints: widget.autofillHints,
      decoration: InputDecoration(
        labelText: widget.label,
        hintText: widget.hint,
        errorText: widget.errorText,
        prefixIcon: widget.prefixIcon == null ? null : Icon(widget.prefixIcon),
        suffixIcon: widget.obscure
            ? IconButton(icon: Icon(_hidden ? Icons.visibility_outlined : Icons.visibility_off_outlined), onPressed: () => setState(() => _hidden = !_hidden))
            : null,
      ),
    );
  }
}
