import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:money_tracker_app/core/home_shell.dart';
import 'package:money_tracker_app/features/budget/models/budget_state.dart';
import 'package:money_tracker_app/features/budget/providers/budget_provider.dart';
import 'package:money_tracker_app/features/budget/screens/budget_screen.dart';
import 'package:money_tracker_app/features/categories/models/category.dart';
import 'package:money_tracker_app/features/categories/providers/category_provider.dart';
import 'package:money_tracker_app/features/dashboard/models/monthly_summary.dart';
import 'package:money_tracker_app/features/dashboard/providers/dashboard_provider.dart';

void main() {
  // BudgetScreen watches budgetControllerProvider directly (for the
  // save-button loading state), which — like transactionEntryControllerProvider
  // and categoryControllerProvider elsewhere in this app — resolves through
  // apiClientProvider to Supabase.instance.client. Supabase.initialize()
  // normally runs in main(), which widget tests never execute, so it's
  // replicated here the same way test/widget_test.dart and the other
  // screen tests under test/features/ do it.
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

  testWidgets(
      'Revisiting the Dashboard tab refetches the summary, proving HomeShell '
      'tears the screen down on tab switch rather than preserving it '
      '(monthlySummaryProvider relies on this to stay fresh — see the '
      'comment on that provider)', (tester) async {
    var fetchCount = 0;
    final summary = MonthlySummary(
      month: '2026-09',
      totalIncome: '1000.00',
      totalExpense: '400.00',
      net: '600.00',
      byCategory: const [],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          monthlySummaryProvider.overrideWith((ref) async {
            fetchCount++;
            return summary;
          }),
          categoryListProvider.overrideWith((ref) async => <Category>[]),
        ],
        child: const MaterialApp(home: HomeShell()),
      ),
    );
    await tester.pump();

    // Initial load of the Dashboard tab fetches once.
    expect(fetchCount, 1);

    // Switch to the Categories tab, then back to Dashboard.
    await tester.tap(find.text('Categories'));
    await tester.pump();
    await tester.tap(find.text('Dashboard'));
    await tester.pump();

    // autoDispose + HomeShell's full teardown on tab switch means revisiting
    // Dashboard triggers a fresh fetch. If HomeShell ever switches to an
    // IndexedStack (preserving tab state), this count would stay at 1 and
    // this test would catch the regression.
    expect(fetchCount, 2);
  });

  testWidgets('Budget tab is present and shows BudgetScreen when selected', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          monthlySummaryProvider.overrideWith((ref) async => MonthlySummary(
                month: '2026-09',
                totalIncome: '0.00',
                totalExpense: '0.00',
                net: '0.00',
                byCategory: const [],
              )),
          categoryListProvider.overrideWith((ref) async => <Category>[]),
          budgetProvider.overrideWith((ref) async => BudgetState(
                incomeTarget: null,
                actualIncomeThisMonth: '0.00',
                lines: const [],
                essentialsBudgetTotal: '0.00',
                discretionaryBudgetTotal: '0.00',
                essentialsActualTotal: '0.00',
                discretionaryActualTotal: '0.00',
                projectedNet: null,
                actualNetSoFar: '0.00',
              )),
          budgetSuggestionsProvider.overrideWith((ref) async => <BudgetSuggestion>[]),
        ],
        child: const MaterialApp(home: HomeShell()),
      ),
    );
    await tester.pump();

    await tester.tap(find.text('Budget'));
    await tester.pump();

    expect(find.byType(BudgetScreen), findsOneWidget);
  });
}
