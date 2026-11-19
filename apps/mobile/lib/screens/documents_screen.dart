import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../data/database.dart';
import '../providers/app_providers.dart';
import '../providers/import.dart';

class DocumentsScreen extends ConsumerWidget {
  const DocumentsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final documentsAsync = ref.watch(documentsProvider);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('МедАрхив'),
        actions: [
          IconButton(
            tooltip: 'Настройки',
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => context.go('/settings'),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showImportSheet(context, ref),
        icon: const Icon(Icons.add),
        label: const Text('Добавить'),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Документы',
                style: theme.textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'Хранятся только на этом устройстве',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 20),
              Expanded(
                child: documentsAsync.when(
                  loading: () => const Center(child: CircularProgressIndicator()),
                  error: (error, _) => Center(child: Text('Ошибка: $error')),
                  data: (documents) {
                    if (documents.isEmpty) {
                      return _EmptyState(onAdd: () => _showImportSheet(context, ref));
                    }
                    return ListView.separated(
                      itemCount: documents.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 12),
                      itemBuilder: (context, index) {
                        final document = documents[index];
                        return _DocumentTile(document: document);
                      },
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showImportSheet(BuildContext context, WidgetRef ref) {
    showModalBottomSheet(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Откуда добавить документы?',
                style: Theme.of(sheetContext).textTheme.titleLarge,
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: () async {
                  Navigator.pop(sheetContext);
                  await _import(context, ref, ImportKind.gallery);
                },
                icon: const Icon(Icons.photo_library_outlined),
                label: const Text('Из галереи'),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: () async {
                  Navigator.pop(sheetContext);
                  await _import(context, ref, ImportKind.file);
                },
                icon: const Icon(Icons.folder_open_outlined),
                label: const Text('Выбрать файлы'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _import(
    BuildContext context,
    WidgetRef ref,
    ImportKind kind,
  ) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final count = await ref.read(documentImportProvider.notifier).pick(kind);
      if (!context.mounted) return;
      if (count > 0) {
        messenger.showSnackBar(
          SnackBar(content: Text('Добавлено документов: $count')),
        );
      }
    } catch (e) {
      if (!context.mounted) return;
      messenger.showSnackBar(
        SnackBar(content: Text('Не удалось импортировать: $e')),
      );
    }
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.onAdd});

  final VoidCallback onAdd;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.folder_off_outlined,
            size: 72,
            color: theme.colorScheme.outline,
          ),
          const SizedBox(height: 16),
          Text(
            'Пока нет документов',
            style: theme.textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          Text(
            'Добавьте снимок или PDF из галереи',
            textAlign: TextAlign.center,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 24),
          FilledButton(onPressed: onAdd, child: const Text('Добавить документ')),
        ],
      ),
    );
  }
}

class _DocumentTile extends StatelessWidget {
  const _DocumentTile({required this.document});

  final DocumentRecord document;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: ListTile(
        contentPadding: const EdgeInsets.all(12),
        leading: _Thumbnail(document: document),
        title: Text(
          document.title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 4),
            Text(
              '${_typeLabel(document.docType)} • ${document.pageCount} стр.',
              style: theme.textTheme.bodySmall,
            ),
            Text(
              DateFormat('d MMM yyyy').format(document.createdAt),
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: () => context.push('/document/${document.id}'),
      ),
    );
  }
}

class _Thumbnail extends StatelessWidget {
  const _Thumbnail({required this.document});

  final DocumentRecord document;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: SizedBox(
        width: 56,
        height: 56,
        child: kIsWeb || document.mimeType == 'application/pdf'
            ? ColoredBox(
                color: theme.colorScheme.primaryContainer,
                child: Icon(
                  document.mimeType == 'application/pdf'
                      ? Icons.picture_as_pdf_outlined
                      : Icons.image_outlined,
                  color: theme.colorScheme.onPrimaryContainer,
                ),
              )
            : ColoredBox(
                color: theme.colorScheme.secondaryContainer,
                child: Icon(
                  Icons.image_outlined,
                  color: theme.colorScheme.onSecondaryContainer,
                ),
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
