import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/legacy.dart';

import '../../../core/api_client.dart';
import '../models/budget_state.dart';

// autoDispose for the same reason as monthlySummaryProvider (see
// dashboard_provider.dart): HomeShell tears this screen down on every tab
// switch, so a plain FutureProvider would go stale after the first load.
final budgetProvider = FutureProvider.autoDispose<BudgetState>((ref) async {
  final apiClient = ref.watch(apiClientProvider);
  final response = await apiClient.dio.get('/budget');
  return BudgetState.fromJson(response.data as Map<String, dynamic>);
});

final budgetSuggestionsProvider = FutureProvider.autoDispose<List<BudgetSuggestion>>((ref) async {
  final apiClient = ref.watch(apiClientProvider);
  final response = await apiClient.dio.get('/budget/suggestions');
  final data = response.data as List<dynamic>;
  return data.map((json) => BudgetSuggestion.fromJson(json as Map<String, dynamic>)).toList();
});

final budgetControllerProvider =
    StateNotifierProvider<BudgetController, AsyncValue<void>>((ref) {
  return BudgetController(ref.watch(apiClientProvider), ref);
});

class BudgetController extends StateNotifier<AsyncValue<void>> {
  BudgetController(this._apiClient, this._ref) : super(const AsyncData(null));

  final ApiClient _apiClient;
  final Ref _ref;

  Future<void> setIncomeTarget(String amount) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await _apiClient.dio.put('/budget/income-target', data: {'amount': amount});
      _ref.invalidate(budgetProvider);
    });
  }

  Future<void> setLine({required String categoryId, required bool isEssential, required String amount}) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await _apiClient.dio.put('/budget/lines', data: {
        'category_id': categoryId,
        'is_essential': isEssential,
        'amount': amount,
      });
      _ref.invalidate(budgetProvider);
    });
  }

  Future<void> acceptSuggestion({required String categoryId, required bool isEssential}) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await _apiClient.dio.post('/budget/lines/accept-suggestion', data: {
        'category_id': categoryId,
        'is_essential': isEssential,
      });
      _ref.invalidate(budgetProvider);
      _ref.invalidate(budgetSuggestionsProvider);
    });
  }
}
