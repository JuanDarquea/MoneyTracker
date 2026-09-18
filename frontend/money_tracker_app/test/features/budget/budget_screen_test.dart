import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:money_tracker_app/core/api_client.dart';
import 'package:money_tracker_app/features/budget/models/budget_state.dart';
import 'package:money_tracker_app/features/budget/providers/budget_provider.dart';
import 'package:money_tracker_app/features/budget/screens/budget_screen.dart';

class _RecordingBudgetController extends BudgetController {
  _RecordingBudgetController(super.apiClient, super.ref);

  String? lastIncomeTargetAmount;
  String? lastLineCategoryId;
  bool? lastLineIsEssential;
  String? lastLineAmount;
  String? lastAcceptedCategoryId;
  bool? lastAcceptedIsEssential;

  @override
  Future<void> setIncomeTarget(String amount) async {
    lastIncomeTargetAmount = amount;
    state = const AsyncData(null);
  }

  @override
  Future<void> setLine({required String categoryId, required bool isEssential, required String amount}) async {
    lastLineCategoryId = categoryId;
    lastLineIsEssential = isEssential;
    lastLineAmount = amount;
    state = const AsyncData(null);
  }

  @override
  Future<void> acceptSuggestion({required String categoryId, required bool isEssential}) async {
    lastAcceptedCategoryId = categoryId;
    lastAcceptedIsEssential = isEssential;
    state = const AsyncData(null);
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

  final essentialLineWithBudget = BudgetLine(
    categoryId: '1',
    categoryName: 'Food',
    isEssential: true,
    budgetAmount: '300.00',
    source: 'manual',
    eligibleForSuggestion: false,
    actualThisMonth: '150.00',
  );

  final discretionaryLineColdStart = BudgetLine(
    categoryId: '1',
    categoryName: 'Food',
    isEssential: false,
    budgetAmount: null,
    source: null,
    eligibleForSuggestion: true,
    actualThisMonth: '40.00',
  );

  final state = BudgetState(
    incomeTarget: '3000.00',
    actualIncomeThisMonth: '1000.00',
    lines: [essentialLineWithBudget, discretionaryLineColdStart],
    essentialsBudgetTotal: '300.00',
    discretionaryBudgetTotal: '0.00',
    essentialsActualTotal: '150.00',
    discretionaryActualTotal: '40.00',
    projectedNet: '2700.00',
    actualNetSoFar: '810.00',
  );

  testWidgets('BudgetScreen renders totals, net figures, and lines', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          budgetProvider.overrideWith((ref) async => state),
          budgetSuggestionsProvider.overrideWith((ref) async => <BudgetSuggestion>[]),
        ],
        child: const MaterialApp(home: BudgetScreen()),
      ),
    );
    await tester.pump();

    expect(find.text('Actual income: 1000.00'), findsOneWidget);
    expect(find.text('Projected net: 2700.00'), findsOneWidget);
    expect(find.text('Actual net so far: 810.00'), findsOneWidget);
    expect(find.textContaining('Food'), findsWidgets);
    expect(find.byKey(const Key('line_progress_1-true')), findsOneWidget);
    expect(find.byKey(const Key('line_amount_field_1-false')), findsOneWidget);
  });

  testWidgets('Saving a manual amount on a cold-start line calls setLine', (tester) async {
    late _RecordingBudgetController controller;

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          budgetProvider.overrideWith((ref) async => state),
          budgetSuggestionsProvider.overrideWith((ref) async => <BudgetSuggestion>[]),
          budgetControllerProvider.overrideWith((ref) {
            controller = _RecordingBudgetController(ref.watch(apiClientProvider), ref);
            return controller;
          }),
        ],
        child: const MaterialApp(home: BudgetScreen()),
      ),
    );
    await tester.pump();

    await tester.enterText(find.byKey(const Key('line_amount_field_1-false')), '120.00');
    await tester.tap(find.byKey(const Key('save_line_button_1-false')));
    await tester.pump();

    expect(controller.lastLineCategoryId, '1');
    expect(controller.lastLineIsEssential, false);
    expect(controller.lastLineAmount, '120.00');
  });

  testWidgets('Accept-suggestion button shows the suggested amount and triggers acceptSuggestion',
      (tester) async {
    late _RecordingBudgetController controller;
    final suggestion = BudgetSuggestion(categoryId: '1', isEssential: false, suggestedAmount: '55.00');

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          budgetProvider.overrideWith((ref) async => state),
          budgetSuggestionsProvider.overrideWith((ref) async => [suggestion]),
          budgetControllerProvider.overrideWith((ref) {
            controller = _RecordingBudgetController(ref.watch(apiClientProvider), ref);
            return controller;
          }),
        ],
        child: const MaterialApp(home: BudgetScreen()),
      ),
    );
    await tester.pump();

    expect(find.text('Use suggestion: 55.00'), findsOneWidget);

    await tester.tap(find.byKey(const Key('accept_suggestion_button_1-false')));
    await tester.pump();

    expect(controller.lastAcceptedCategoryId, '1');
    expect(controller.lastAcceptedIsEssential, false);
  });

  testWidgets(
      'Tapping the edit icon on a line with a budget reveals a pre-filled input, and saving calls setLine',
      (tester) async {
    late _RecordingBudgetController controller;

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          budgetProvider.overrideWith((ref) async => state),
          budgetSuggestionsProvider.overrideWith((ref) async => <BudgetSuggestion>[]),
          budgetControllerProvider.overrideWith((ref) {
            controller = _RecordingBudgetController(ref.watch(apiClientProvider), ref);
            return controller;
          }),
        ],
        child: const MaterialApp(home: BudgetScreen()),
      ),
    );
    await tester.pump();

    // Line 1-true has a budget of 300.00 -- cold-start input is not shown,
    // only the read-only progress display and an edit icon.
    expect(find.byKey(const Key('line_progress_1-true')), findsOneWidget);
    expect(find.byKey(const Key('line_amount_field_1-true')), findsNothing);
    expect(find.byKey(const Key('edit_line_button_1-true')), findsOneWidget);

    await tester.tap(find.byKey(const Key('edit_line_button_1-true')));
    await tester.pump();

    final input = tester.widget<TextField>(find.byKey(const Key('line_amount_field_1-true')));
    expect(input.controller?.text, '300.00');

    await tester.enterText(find.byKey(const Key('line_amount_field_1-true')), '350.00');
    await tester.tap(find.byKey(const Key('save_line_button_1-true')));
    await tester.pump();

    expect(controller.lastLineCategoryId, '1');
    expect(controller.lastLineIsEssential, true);
    expect(controller.lastLineAmount, '350.00');
  });

  testWidgets('An archived-category line with a budget shows no interactive controls', (tester) async {
    final archivedLineWithBudget = BudgetLine(
      categoryId: '2',
      categoryName: 'Old Category',
      isEssential: true,
      budgetAmount: '200.00',
      source: 'manual',
      eligibleForSuggestion: true,
      actualThisMonth: '50.00',
      isArchived: true,
    );
    final archivedState = BudgetState(
      incomeTarget: '3000.00',
      actualIncomeThisMonth: '1000.00',
      lines: [archivedLineWithBudget],
      essentialsBudgetTotal: '200.00',
      discretionaryBudgetTotal: '0.00',
      essentialsActualTotal: '50.00',
      discretionaryActualTotal: '0.00',
      projectedNet: '2800.00',
      actualNetSoFar: '950.00',
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          budgetProvider.overrideWith((ref) async => archivedState),
          budgetSuggestionsProvider.overrideWith(
            (ref) async => [BudgetSuggestion(categoryId: '2', isEssential: true, suggestedAmount: '99.00')],
          ),
        ],
        child: const MaterialApp(home: BudgetScreen()),
      ),
    );
    await tester.pump();

    expect(find.byKey(const Key('line_progress_2-true')), findsOneWidget);
    expect(find.text('50.00 / 200.00'), findsOneWidget);
    expect(find.byKey(const Key('edit_line_button_2-true')), findsNothing);
    expect(find.byKey(const Key('line_amount_field_2-true')), findsNothing);
    expect(find.byKey(const Key('save_line_button_2-true')), findsNothing);
    expect(find.byKey(const Key('accept_suggestion_button_2-true')), findsNothing);
  });

  testWidgets('An archived-category line with no budget shows a read-only 0.00 display and no controls',
      (tester) async {
    final archivedLineNoBudget = BudgetLine(
      categoryId: '3',
      categoryName: 'Retired Category',
      isEssential: false,
      budgetAmount: null,
      source: null,
      eligibleForSuggestion: true,
      actualThisMonth: '10.00',
      isArchived: true,
    );
    final archivedState = BudgetState(
      incomeTarget: '3000.00',
      actualIncomeThisMonth: '1000.00',
      lines: [archivedLineNoBudget],
      essentialsBudgetTotal: '0.00',
      discretionaryBudgetTotal: '0.00',
      essentialsActualTotal: '0.00',
      discretionaryActualTotal: '10.00',
      projectedNet: '3000.00',
      actualNetSoFar: '990.00',
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          budgetProvider.overrideWith((ref) async => archivedState),
          budgetSuggestionsProvider.overrideWith((ref) async => <BudgetSuggestion>[]),
        ],
        child: const MaterialApp(home: BudgetScreen()),
      ),
    );
    await tester.pump();

    expect(find.byKey(const Key('line_progress_3-false')), findsOneWidget);
    expect(find.text('10.00 / 0.00'), findsOneWidget);
    expect(find.byKey(const Key('edit_line_button_3-false')), findsNothing);
    expect(find.byKey(const Key('line_amount_field_3-false')), findsNothing);
    expect(find.byKey(const Key('save_line_button_3-false')), findsNothing);
    expect(find.byKey(const Key('accept_suggestion_button_3-false')), findsNothing);
  });

  testWidgets('Saving the income target calls setIncomeTarget', (tester) async {
    late _RecordingBudgetController controller;

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          budgetProvider.overrideWith((ref) async => state),
          budgetSuggestionsProvider.overrideWith((ref) async => <BudgetSuggestion>[]),
          budgetControllerProvider.overrideWith((ref) {
            controller = _RecordingBudgetController(ref.watch(apiClientProvider), ref);
            return controller;
          }),
        ],
        child: const MaterialApp(home: BudgetScreen()),
      ),
    );
    await tester.pump();

    await tester.enterText(find.byKey(const Key('income_target_field')), '3500.00');
    await tester.tap(find.byKey(const Key('save_income_target_button')));
    await tester.pump();

    expect(controller.lastIncomeTargetAmount, '3500.00');
  });
}
