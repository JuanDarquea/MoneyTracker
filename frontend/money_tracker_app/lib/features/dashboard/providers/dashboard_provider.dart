import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../models/monthly_summary.dart';

// autoDispose is required here: HomeShell tears down this screen's whole
// widget tree on every tab switch (body: _screens[_index], not an
// IndexedStack), so this provider must refetch fresh each time the
// Dashboard tab is revisited. If HomeShell is ever changed to preserve
// tab state (e.g. via IndexedStack), this provider needs an explicit
// invalidation trigger instead, or the dashboard will silently show
// stale data again.
final monthlySummaryProvider = FutureProvider.autoDispose<MonthlySummary>((ref) async {
  final apiClient = ref.watch(apiClientProvider);
  final response = await apiClient.dio.get('/summary');
  return MonthlySummary.fromJson(response.data as Map<String, dynamic>);
});
