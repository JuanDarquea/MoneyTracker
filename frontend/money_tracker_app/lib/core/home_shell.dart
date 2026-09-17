import 'package:flutter/material.dart';

import '../features/categories/screens/category_list_screen.dart';
import '../features/dashboard/screens/dashboard_screen.dart';
import '../features/transactions/screens/transaction_entry_screen.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  static const _screens = [
    DashboardScreen(),
    TransactionEntryScreen(),
    CategoryListScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _screens[_index],
      bottomNavigationBar: NavigationBar(
        key: const Key('home_bottom_nav'),
        selectedIndex: _index,
        onDestinationSelected: (value) => setState(() => _index = value),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.dashboard), label: 'Dashboard'),
          NavigationDestination(icon: Icon(Icons.add_circle), label: 'Add'),
          NavigationDestination(icon: Icon(Icons.category), label: 'Categories'),
        ],
      ),
    );
  }
}
