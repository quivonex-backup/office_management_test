import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';

import '../../api/api_request.dart';

/// Picks one file (photo, document). Reports an [UploadFile] with the given form [field].
class FilePickerField extends StatelessWidget {
  final String label, field;
  final UploadFile? value;
  final void Function(UploadFile?) onChanged;
  final bool imagesOnly;
  const FilePickerField({super.key, required this.label, required this.field, required this.value, required this.onChanged, this.imagesOnly = false});

  Future<void> _pick() async {
    // the browser gives no file path, so on web the bytes are read instead
    final r = await FilePicker.platform.pickFiles(type: imagesOnly ? FileType.image : FileType.any, withData: kIsWeb);
    if (r == null || r.files.isEmpty) return;
    final f = r.files.single;
    if (kIsWeb ? f.bytes == null : f.path == null) return;
    onChanged(UploadFile(field: field, name: f.name, path: kIsWeb ? null : f.path, bytes: kIsWeb ? f.bytes : null));
  }

  @override
  Widget build(BuildContext context) => InkWell(
        onTap: _pick,
        borderRadius: BorderRadius.circular(12),
        child: InputDecorator(
          decoration: InputDecoration(
            labelText: label,
            suffixIcon: value == null
                ? const Icon(Icons.attach_file)
                : IconButton(icon: const Icon(Icons.clear, size: 18), onPressed: () => onChanged(null)),
          ),
          child: Text(value?.name ?? 'Tap to choose a file', maxLines: 1, overflow: TextOverflow.ellipsis),
        ),
      );
}
