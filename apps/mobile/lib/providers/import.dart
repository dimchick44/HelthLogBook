import 'package:file_picker/file_picker.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path/path.dart' as p;
import 'package:uuid/uuid.dart';

import '../data/database.dart';
import '../services/document_store.dart';
import 'app_providers.dart';

enum ImportKind { gallery, file }

class ImportSource {
  const ImportSource({
    required this.path,
    required this.title,
    required this.mimeType,
    required this.pageCount,
  });

  final String path;
  final String title;
  final String mimeType;
  final int pageCount;
}

class DocumentImport extends Notifier<bool> {
  @override
  bool build() => false;

  Future<int> pick(ImportKind kind) async {
    state = true;
    var imported = 0;
    try {
      final sources = switch (kind) {
        ImportKind.gallery => await _pickFromGallery(),
        ImportKind.file => await _pickFiles(),
      };
      for (final source in sources) {
        final storedPath = await storeDocument(source.path);
        final id = const Uuid().v4();
        final now = DateTime.now();
        ref.read(appDatabaseProvider).insertDocument(
              DocumentRecord(
                id: id,
                title: source.title,
                sourcePath: storedPath,
                mimeType: source.mimeType,
                docType: 'unknown',
                recognizedText: '',
                createdAt: now,
                updatedAt: now,
                pageCount: source.pageCount,
              ),
            );
        imported++;
      }
      ref.invalidate(documentsProvider);
      return imported;
    } finally {
      state = false;
    }
  }

  Future<List<ImportSource>> _pickFromGallery() async {
    final images = await ImagePicker().pickMultiImage();
    return [
      for (final image in images)
        ImportSource(
          path: image.path,
          title: p.basenameWithoutExtension(image.name),
          mimeType: _mimeFromPath(image.path),
          pageCount: 1,
        ),
    ];
  }

  Future<List<ImportSource>> _pickFiles() async {
    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: FileType.custom,
      allowedExtensions: ['pdf', 'jpg', 'jpeg', 'png', 'heic'],
    );
    return [
      for (final file in result?.files ?? <PlatformFile>[])
        if (file.path != null)
          ImportSource(
            path: file.path!,
            title: p.basenameWithoutExtension(file.name),
            mimeType: _mimeFromPath(file.path!),
            pageCount: 1,
          ),
    ];
  }

  String _mimeFromPath(String path) {
    final extension = p.extension(path).toLowerCase();
    return switch (extension) {
      '.pdf' => 'application/pdf',
      '.jpg' || '.jpeg' => 'image/jpeg',
      '.png' => 'image/png',
      '.heic' => 'image/heic',
      _ => 'application/octet-stream',
    };
  }
}

final documentImportProvider =
    NotifierProvider<DocumentImport, bool>(DocumentImport.new);
