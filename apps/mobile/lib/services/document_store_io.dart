import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

Future<String> storeDocument(String path) async {
  final base = await getApplicationDocumentsDirectory();
  final directory = Directory(p.join(base.path, 'documents'));
  if (!await directory.exists()) {
    await directory.create(recursive: true);
  }
  final extension = p.extension(path);
  final storedPath =
      p.join(directory.path, '${DateTime.now().microsecondsSinceEpoch}$extension');
  await File(path).copy(storedPath);
  return storedPath;
}

bool documentFileExists(String path) => File(path).existsSync();

Future<void> deleteDocumentFile(String path) async {
  final file = File(path);
  if (await file.exists()) {
    await file.delete();
  }
}
