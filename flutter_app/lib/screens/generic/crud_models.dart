import 'package:flutter/material.dart';

import '../../api/api_request.dart';
import '../../api/api_response.dart';
import '../../widgets/forms/opt.dart';

enum FieldType { text, multiline, integer, decimal, email, phone, password, date, time, dropdown, boolean, file, image }

/// One input of a create/edit form. [key] is the exact backend payload key.
class FieldSpec {
  final String key, label;
  final FieldType type;
  final bool required;
  final List<Opt>? options;
  final Future<List<Opt>> Function()? loadOptions;
  final String? Function(String?)? validator;
  final dynamic initial;

  /// shown/sent only when creating (e.g. employee_id on an assignment)
  final bool createOnly;

  /// shown/sent only when editing
  final bool editOnly;

  /// edit prefill when the item's shape differs from the payload (e.g. item['branch']['id'] -> branch_id)
  final dynamic Function(Map<String, dynamic> item)? readValue;

  /// when the user clears a dropdown/number on edit, send null (backend clears it)
  final bool clearable;
  final String? hint;

  const FieldSpec(
    this.key,
    this.label, {
    this.type = FieldType.text,
    this.required = false,
    this.options,
    this.loadOptions,
    this.validator,
    this.initial,
    this.createOnly = false,
    this.editOnly = false,
    this.readValue,
    this.clearable = false,
    this.hint,
  });
}

class FilterSpec {
  final String key, label;
  final List<Opt>? options;
  final Future<List<Opt>> Function()? loadOptions;
  const FilterSpec(this.key, this.label, {this.options, this.loadOptions});
}

typedef Item = Map<String, dynamic>;

/// Describes a whole list + create/edit/deactivate module. One config -> one working screen.
class CrudConfig {
  final String title;
  final IconData icon;

  /// loads the list; [filters] holds search / dropdown filters / active flag
  final Future<ApiResult<dynamic>> Function(Map<String, dynamic> filters) list;
  final Future<ApiResult<dynamic>> Function(Map<String, dynamic> body, List<UploadFile> files)? create;
  final Future<ApiResult<dynamic>> Function(Item item, Map<String, dynamic> body, List<UploadFile> files)? update;
  final Future<ApiResult<dynamic>> Function(Item item)? deactivate;
  final List<FieldSpec> fields;
  final String Function(Item) titleOf;
  final String? Function(Item)? subtitleOf;
  final String? Function(Item)? badgeOf;
  final String? Function(Item)? trailingOf;

  /// permission codes (any) needed to create/edit/deactivate. Empty = everyone.
  final List<String> managePerms;
  final bool hasSearch;

  /// 'is_active' -> toggle sends is_active:true when off; 'include_inactive' -> toggle sends it when on; null = no toggle
  final String? activeFilterKey;
  final List<FilterSpec> filters;
  final Map<String, dynamic> baseFilters;
  final String createLabel;
  final String deactivateLabel;
  final String deactivateWarning;

  /// when set, tapping a row opens this instead of the edit form
  final void Function(BuildContext context, Item item, Future<void> Function() reload)? onTap;

  /// extra per-row menu actions (label -> callback). Return true to reload.
  final List<RowAction> rowActions;
  final String emptyMessage;

  /// extra widgets shown above the list (summary chips etc.)
  final Widget Function(BuildContext context, ApiResult<dynamic> lastResult)? header;

  const CrudConfig({
    required this.title,
    required this.list,
    required this.titleOf,
    this.icon = Icons.list_alt_outlined,
    this.create,
    this.update,
    this.deactivate,
    this.fields = const [],
    this.subtitleOf,
    this.badgeOf,
    this.trailingOf,
    this.managePerms = const [],
    this.hasSearch = true,
    this.activeFilterKey,
    this.filters = const [],
    this.baseFilters = const {},
    this.createLabel = 'Add',
    this.deactivateLabel = 'Deactivate',
    this.deactivateWarning = 'It will no longer be available for new use.',
    this.onTap,
    this.rowActions = const [],
    this.emptyMessage = 'Nothing here yet.',
    this.header,
  });
}

class RowAction {
  final String label;
  final IconData icon;
  final bool Function(Item item)? visible;
  final Future<bool> Function(BuildContext context, Item item) run;
  const RowAction(this.label, this.icon, this.run, {this.visible});
}
