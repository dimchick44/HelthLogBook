import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/database.dart';

final appDatabaseProvider = Provider<AppDatabase>((ref) {
  return AppDatabase();
});

List<DocumentRecord> _demoDocuments() {
  final now = DateTime.now();
  return [
    DocumentRecord(
      id: 'demo-1',
      title: 'Общий анализ крови',
      sourcePath: '',
      mimeType: 'application/pdf',
      docType: 'analysis',
      recognizedText:
          'ОБЩИЙ АНАЛИЗ КРОВИ\nГемоглобин 134 г/л\nЛейкоциты 6,2 ×10⁹/л\nЭритроциты 4,5 ×10¹²/л',
      organization: 'Лаборатория Инвитро',
      documentDate: '18.11.2026',
      createdAt: now.subtract(const Duration(days: 1)),
      updatedAt: now.subtract(const Duration(days: 1)),
      pageCount: 2,
    ),
    DocumentRecord(
      id: 'demo-2',
      title: 'Заключение кардиолога',
      sourcePath: '',
      mimeType: 'image/jpeg',
      docType: 'conclusion',
      recognizedText:
          'ЗАКЛЮЧЕНИЕ КАРДИОЛОГА\nЭКГ: синусовый ритм.\nРекомендовано повторить через 3 месяца.',
      organization: 'Клиника «Сердце»',
      documentDate: '12.11.2026',
      createdAt: now.subtract(const Duration(days: 7)),
      updatedAt: now.subtract(const Duration(days: 7)),
      pageCount: 1,
    ),
    DocumentRecord(
      id: 'demo-3',
      title: 'Назначение терапевта',
      sourcePath: '',
      mimeType: 'application/pdf',
      docType: 'prescription',
      recognizedText:
          'НАЗНАЧЕНИЕ\nПрепарат: витамин D 2000 МЕ\nПриём: 1 раз в день во время еды.',
      organization: 'Поликлиника №12',
      documentDate: '05.11.2026',
      createdAt: now.subtract(const Duration(days: 14)),
      updatedAt: now.subtract(const Duration(days: 14)),
      pageCount: 1,
    ),
  ];
}

final documentsProvider = FutureProvider<List<DocumentRecord>>((ref) async {
  if (kIsWeb) return _demoDocuments();
  return ref.watch(appDatabaseProvider).readAllDocuments();
});

final documentProvider =
    FutureProvider.family<DocumentRecord?, String>((ref, id) async {
  if (kIsWeb) {
    for (final item in _demoDocuments()) {
      if (item.id == id) return item;
    }
    return null;
  }
  return ref.watch(appDatabaseProvider).findDocument(id);
});
