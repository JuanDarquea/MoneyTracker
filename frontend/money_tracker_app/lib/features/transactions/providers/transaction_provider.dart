import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/legacy.dart';

import '../../../core/api_client.dart';
import '../models/transaction.dart';

final transactionEntryControllerProvider =
    StateNotifierProvider<TransactionEntryController, AsyncValue<void>>((ref) {
  return TransactionEntryController(ref.watch(apiClientProvider));
});

class TransactionEntryController extends StateNotifier<AsyncValue<void>> {
  TransactionEntryController(this._apiClient) : super(const AsyncData(null));

  final ApiClient _apiClient;

  Future<void> submit(TransactionDraft draft) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => _apiClient.dio.post('/transactions', data: draft.toJson()),
    );
  }
}
