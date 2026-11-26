import 'package:flutter/material.dart';

class Home extends StatefulWidget {
  const Home({super.key});
  @override
  State<Home> createState() => _HomeState();
}

class _HomeState extends State<Home> {
  late final Future<List<String>> _budgets = loadBudgets();

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    debugPrint('width $width');
    return FutureBuilder(
      future: _budgets,
      builder: (context, snapshot) => ListView.builder(
        itemCount: snapshot.data?.length ?? 0,
        itemBuilder: (context, i) => Text(snapshot.data![i]),
      ),
    );
  }
}

Future<List<String>> loadBudgets() async => ['https://api.example.com/v1'];
