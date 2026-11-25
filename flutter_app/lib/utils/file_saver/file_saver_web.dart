import 'dart:js_interop';
import 'dart:typed_data';

import 'package:web/web.dart' as web;

/// Web: the browser downloads the file (anchor click on a blob URL). Returns an error text or null.
Future<String?> saveFile(String filename, Uint8List bytes) async {
  final blob = web.Blob([bytes.toJS].toJS);
  final url = web.URL.createObjectURL(blob);
  final a = web.HTMLAnchorElement()
    ..href = url
    ..download = filename;
  a.click();
  web.URL.revokeObjectURL(url);
  return null;
}
