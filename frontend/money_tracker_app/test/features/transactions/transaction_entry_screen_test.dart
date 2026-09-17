import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:money_tracker_app/features/categories/models/category.dart';
import 'package:money_tracker_app/features/categories/providers/category_provider.dart';
import 'package:money_tracker_app/features/transactions/screens/transaction_entry_screen.dart';

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

  final fakeCategories = [
    Category(id: '1', name: 'Food', type: 'expense', isArchived: false),
    Category(id: '2', name: 'Salary', type: 'income', isArchived: false),
  ];

  testWidgets('TransactionEntryScreen exposes exactly the required fields',
      (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [categoryListProvider.overrideWith((ref) async => fakeCategories)],
        child: const MaterialApp(home: TransactionEntryScreen()),
      ),
    );
    await tester.pump();

    expect(find.byKey(const Key('amount_field')), findsOneWidget);
    expect(find.byKey(const Key('type_toggle')), findsOneWidget);
    expect(find.byKey(const Key('category_dropdown')), findsOneWidget);
    expect(find.byKey(const Key('essential_toggle')), findsOneWidget);
    expect(find.byKey(const Key('date_field')), findsOneWidget);
    expect(find.byKey(const Key('note_field')), findsOneWidget);
    expect(find.byKey(const Key('submit_button')), findsOneWidget);
  });

  testWidgets('Essential/Discretionary toggle only shows for expense type',
      (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [categoryListProvider.overrideWith((ref) async => fakeCategories)],
        child: const MaterialApp(home: TransactionEntryScreen()),
      ),
    );
    await tester.pump();

    expect(find.byKey(const Key('essential_toggle')), findsOneWidget);

    await tester.tap(find.text('Income'));
    await tester.pump();

    expect(find.byKey(const Key('essential_toggle')), findsNothing);
  });

  testWidgets('Category dropdown only shows categories matching the selected type',
      (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [categoryListProvider.overrideWith((ref) async => fakeCategories)],
        child: const MaterialApp(home: TransactionEntryScreen()),
      ),
    );
    await tester.pump();

    expect(find.text('Food'), findsOneWidget);
    expect(find.text('Salary'), findsNothing);

    await tester.tap(find.text('Income'));
    await tester.pump();

    expect(find.text('Salary'), findsOneWidget);
  });

  testWidgets(
      'Submitting with no category available for the selected type shows feedback instead of doing nothing',
      (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [categoryListProvider.overrideWith((ref) async => <Category>[])],
        child: const MaterialApp(home: TransactionEntryScreen()),
      ),
    );
    await tester.pump();

    await tester.tap(find.byKey(const Key('submit_button')));
    await tester.pump();

    expect(find.text('No category available for this type'), findsOneWidget);
  });
}
