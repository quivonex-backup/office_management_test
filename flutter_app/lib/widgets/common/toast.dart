import 'package:flutter/material.dart';

import '../../api/api_response.dart';
import '../../constants/app_colors.dart';

/// Snackbar notifications (React Toast).
class Toast {
  Toast._();

  static void show(BuildContext context, String message, {bool error = false}) {
    if (message.trim().isEmpty) return;
    final m = ScaffoldMessenger.maybeOf(context);
    m?.hideCurrentSnackBar();
    m?.showSnackBar(SnackBar(
      content: Text(message),
      backgroundColor: error ? AppColors.danger : AppColors.success,
      duration: Duration(seconds: error ? 5 : 3),
    ));
  }

  /// Shows the server message (and failure reasons) of a result.
  static void result(BuildContext context, ApiResult<dynamic> r, {String? success}) {
    if (r.ok) {
      show(context, success ?? (r.message.isNotEmpty ? r.message : 'Done.'));
    } else {
      show(context, r.fullMessage.isNotEmpty ? r.fullMessage : 'Something went wrong.', error: true);
    }
  }
}
