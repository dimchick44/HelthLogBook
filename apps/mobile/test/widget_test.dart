import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:medarchive/app.dart';
import 'package:medarchive/providers/app_providers.dart';

void main() {
  testWidgets('shows documents screen shell', (WidgetTester tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          documentsProvider.overrideWith((ref) async => const []),
        ],
        child: const MedArchiveApp(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('МедАрхив'), findsWidgets);
    expect(find.text('Документы'), findsOneWidget);
    expect(find.text('Пока нет документов'), findsOneWidget);
  });
}
