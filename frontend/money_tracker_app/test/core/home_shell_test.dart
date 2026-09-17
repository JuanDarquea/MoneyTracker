import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:money_tracker_app/core/home_shell.dart';
import 'package:money_tracker_app/features/categories/models/category.dart';
import 'package:money_tracker_app/features/categories/providers/category_provider.dart';
import 'package:money_tracker_app/features/dashboard/models/monthly_summary.dart';
import 'package:money_tracker_app/features/dashboard/providers/dashboard_provider.dart';

void main() {
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
}
