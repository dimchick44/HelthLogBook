import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'screens/document_detail_screen.dart';
import 'screens/documents_screen.dart';
import 'screens/settings_screen.dart';
import 'theme/app_theme.dart';

final _router = GoRouter(
  routes: [
    GoRoute(
      path: '/',
      builder: (context, state) => const DocumentsScreen(),
      routes: [
        GoRoute(
          path: 'document/:id',
          builder: (context, state) =>
              DocumentDetailScreen(id: state.pathParameters['id']!),
        ),
        GoRoute(
          path: 'settings',
          builder: (context, state) => const SettingsScreen(),
        ),
      ],
    ),
  ],
);

class MedArchiveApp extends StatelessWidget {
  const MedArchiveApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'МедАрхив',
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      routerConfig: _router,
    );
  }
}
