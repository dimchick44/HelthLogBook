import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../data/database.dart';
import '../providers/app_providers.dart';
import '../services/document_store.dart';

class DocumentDetailScreen extends ConsumerWidget {
  const DocumentDetailScreen({super.key, required this.id});

  final String id;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final documentAsync = ref.watch(documentProvider(id));
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Документ'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
        actions: [
          documentAsync.maybeWhen(
            data: (document) => document == null
                ? const SizedBox.shrink()
                : IconButton(
                    tooltip: 'Удалить',
                    icon: const Icon(Icons.delete_outline),
                    onPressed: () => _confirmDelete(context, ref, document),
                  ),
            orElse: () => const SizedBox.shrink(),
          ),
        ],
      ),
      body: SafeArea(
        child: documentAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => Center(child: Text('Ошибка: $error')),
          data: (document) {
            if (document == null) {
              return const Center(child: Text('Документ не найден'));
            }
            return SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _Preview(document: document),
                  const SizedBox(height: 16),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            document.title,
                            style: theme.textTheme.titleLarge,
                          ),
                          const SizedBox(height: 8),
                          _InfoRow(
                            label: 'Тип',
                            value: _typeLabel(document.docType),
                          ),
                          _InfoRow(
                            label: 'Дата документа',
                            value: document.documentDate ?? 'не указана',
                          ),
                          _InfoRow(
                            label: 'Организация',
                            value: document.organization ?? 'не указана',
                          ),
                          _InfoRow(
                            label: 'Добавлен',
                            value: DateFormat('d MMMM yyyy, HH:mm', 'ru')
                                .format(document.createdAt.toLocal()),
                          ),
                          _InfoRow(label: 'Файл', value: document.mimeType),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Распознанный текст',
                    style: theme.textTheme.titleMedium,
                  ),
                  const SizedBox(height: 8),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Text(
                        document.recognizedText.isEmpty
                            ? 'Распознавание ещё не выполнялось. Локальный OCR будет добавлен на следующем шаге.'
                            : document.recognizedText,
                        style: theme.textTheme.bodyMedium,
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  OutlinedButton.icon(
                    onPressed: () {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('OCR будет добавлен на следующем шаге'),
                        ),
                      );
                    },
                    icon: const Icon(Icons.text_fields),
                    label: const Text('Распознать текст'),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  Future<void> _confirmDelete(
    BuildContext context,
    WidgetRef ref,
    DocumentRecord document,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Удалить документ?'),
        content: const Text(
          'Файл и данные документа будут удалены с этого устройства.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Отмена'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Удалить'),
          ),
        ],
      ),
    );
    if (confirmed != true || !context.mounted) return;

    await deleteDocumentFile(document.sourcePath);
    ref.read(appDatabaseProvider).deleteDocument(document.id);
    ref.invalidate(documentsProvider);
    if (context.mounted) context.pop();
  }
}

class _Preview extends StatelessWidget {
  const _Preview({required this.document});

  final DocumentRecord document;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      height: 160,
      decoration: BoxDecoration(
        color: theme.colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              document.mimeType == 'application/pdf'
                  ? Icons.picture_as_pdf_outlined
                  : Icons.image_outlined,
              size: 48,
              color: theme.colorScheme.onPrimaryContainer,
            ),
            const SizedBox(height: 8),
            Text(
              document.mimeType == 'application/pdf'
                  ? 'PDF-документ'
                  : 'Изображение документа',
              style: TextStyle(color: theme.colorScheme.onPrimaryContainer),
            ),
          ],
        ),
      ),
    );
  }
}

String _typeLabel(String type) => switch (type) {
      'analysis' => 'Анализы',
      'conclusion' => 'Заключение',
      'prescription' => 'Назначение',
      'patient' => 'Карта пациента',
      _ => 'Документ',
    };

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          SizedBox(
            width: 130,
            child: Text(
              label,
              style: TextStyle(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }
}
