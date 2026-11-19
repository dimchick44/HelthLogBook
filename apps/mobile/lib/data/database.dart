class DocumentRecord {
  const DocumentRecord({
    required this.id,
    required this.title,
    required this.sourcePath,
    required this.mimeType,
    required this.docType,
    required this.recognizedText,
    this.organization,
    this.documentDate,
    required this.createdAt,
    required this.updatedAt,
    required this.pageCount,
  });

  final String id;
  final String title;
  final String sourcePath;
  final String mimeType;
  final String docType;
  final String recognizedText;
  final String? organization;
  final String? documentDate;
  final DateTime createdAt;
  final DateTime updatedAt;
  final int pageCount;
}

/// Простое локальное хранилище для прототипа.
///
/// Позже заменяется на Drift/SQLite без изменения UI-слоя.
class AppDatabase {
  final List<DocumentRecord> _documents = [];

  List<DocumentRecord> readAllDocuments() => List.unmodifiable(_documents);

  DocumentRecord? findDocument(String id) {
    for (final document in _documents) {
      if (document.id == id) return document;
    }
    return null;
  }

  void insertDocument(DocumentRecord document) => _documents.add(document);

  void deleteDocument(String id) => _documents.removeWhere((d) => d.id == id);
}
