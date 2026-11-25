import 'dart:io';
import 'dart:typed_data';

import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';

/// Android: write to the temp folder, then open with the device's viewer. Returns an error text or null.
Future<String?> saveFile(String filename, Uint8List bytes) async {
  final dir = await getTemporaryDirectory();
  final f = File('${dir.path}/$filename');
  await f.writeAsBytes(bytes, flush: true);
  final r = await OpenFilex.open(f.path);
  return r.type == ResultType.done ? null : r.message;
}
