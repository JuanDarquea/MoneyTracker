import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/legacy.dart';

import '../../../core/api_client.dart';
import '../models/category.dart';

final categoryListProvider = FutureProvider<List<Category>>((ref) async {
  final apiClient = ref.watch(apiClientProvider);
  final response = await apiClient.dio.get('/categories');
  final data = response.data as List<dynamic>;
  return data.map((json) => Category.fromJson(json as Map<String, dynamic>)).toList();
});

final categoryControllerProvider =
    StateNotifierProvider<CategoryController, AsyncValue<void>>((ref) {
  return CategoryController(ref.watch(apiClientProvider), ref);
});

class CategoryController extends StateNotifier<AsyncValue<void>> {
  CategoryController(this._apiClient, this._ref) : super(const AsyncData(null));

  final ApiClient _apiClient;
  final Ref _ref;

  Future<void> create({required String name, required String type, bool? isEssential}) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await _apiClient.dio.post('/categories', data: {
        'name': name,
        'type': type,
        if (isEssential != null) 'is_essential': isEssential,
      });
      _ref.invalidate(categoryListProvider);
    });
  }

  Future<void> archive(String categoryId) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await _apiClient.dio.patch('/categories/$categoryId', data: {'is_archived': true});
      _ref.invalidate(categoryListProvider);
    });
  }

  Future<void> setEssential(String categoryId, bool isEssential) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await _apiClient.dio.patch('/categories/$categoryId', data: {'is_essential': isEssential});
      _ref.invalidate(categoryListProvider);
    });
  }
}
