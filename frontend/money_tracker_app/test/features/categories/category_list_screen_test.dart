import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:money_tracker_app/core/api_client.dart';
import 'package:money_tracker_app/features/categories/models/category.dart';
import 'package:money_tracker_app/features/categories/providers/category_provider.dart';
import 'package:money_tracker_app/features/categories/screens/category_list_screen.dart';

/// A CategoryController stand-in whose `archive` always fails, so the test
/// can assert the failure surfaces to the user instead of vanishing silently.
class _FailingCategoryController extends CategoryController {
  _FailingCategoryController(super.apiClient, super.ref);

  @override
  Future<void> archive(String categoryId) async {
    state = const AsyncLoading();
    state = AsyncError<void>(Exception('network error'), StackTrace.empty);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const sharedPreferencesChannel = MethodChannel('plugins.flutter.io/shared_preferences');
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(sharedPreferencesChannel, (call) async {
    if (call.method == 'getAll') return <String, dynamic>{};
    return null;
  });

  setUpAll(() async {
    await Supabase.initialize(url: 'http://localhost:54321', publishableKey: 'test-anon-key');
  });

  testWidgets('CategoryListScreen renders fetched categories without an essential toggle',
      (tester) async {
    final categories = [
      Category(id: '1', name: 'Food', type: 'expense', isArchived: false),
      Category(id: '2', name: 'Salary', type: 'income', isArchived: false),
    ];

    await tester.pumpWidget(
      ProviderScope(
        overrides: [categoryListProvider.overrideWith((ref) async => categories)],
        child: const MaterialApp(home: CategoryListScreen()),
      ),
    );
    await tester.pump();

    expect(find.text('Food'), findsOneWidget);
    expect(find.text('Salary'), findsOneWidget);
    expect(find.byKey(const Key('essential_toggle_1')), findsNothing);
    expect(find.byKey(const Key('add_category_button')), findsOneWidget);
  });

  testWidgets(
      'CategoryListScreen shows a SnackBar when a category mutation fails',
      (tester) async {
    final categories = [
      Category(id: '1', name: 'Food', type: 'expense', isArchived: false),
    ];

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          categoryListProvider.overrideWith((ref) async => categories),
          categoryControllerProvider.overrideWith(
            (ref) => _FailingCategoryController(ref.watch(apiClientProvider), ref),
          ),
        ],
        child: const MaterialApp(home: CategoryListScreen()),
      ),
    );
    await tester.pump();

    await tester.tap(find.byKey(const Key('archive_button_1')));
    await tester.pump();

    expect(find.textContaining('Failed to update category'), findsOneWidget);
  });
}
