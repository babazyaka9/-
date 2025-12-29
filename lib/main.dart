import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  runApp(const AnatomyApp());
}

class AnatomyApp extends StatelessWidget {
  const AnatomyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Анатомія',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        useMaterial3: true,
      ),
      home: const MenuScreen(),
    );
  }
}

// --- ГОЛОВНЕ МЕНЮ ---
class MenuScreen extends StatefulWidget {
  const MenuScreen({super.key});

  @override
  State<MenuScreen> createState() => _MenuScreenState();
}

class _MenuScreenState extends State<MenuScreen> {
  List<dynamic> _questions = [];
  Map<String, dynamic> _progress = {};
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    try {
      // 1. Завантажуємо питання з файлу
      final jsonString = await rootBundle.loadString('questions.json');
      final List<dynamic> data = json.decode(jsonString);

      // 2. Завантажуємо прогрес
      final prefs = await SharedPreferences.getInstance();
      final savedProgress = prefs.getString('user_progress');
      Map<String, dynamic> progressMap = {
        "wrong_indices": [],
        "chunk_results": {}
      };
      
      if (savedProgress != null) {
        progressMap = json.decode(savedProgress);
      }

      if (mounted) {
        setState(() {
          _questions = data;
          _progress = progressMap;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _resetProgress() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('user_progress');
    _loadData(); // Перезавантажити
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    if (_error != null) {
      return Scaffold(
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(20.0),
            child: Text("Помилка: $_error\nПеревірте файл questions.json", 
              style: const TextStyle(color: Colors.red), textAlign: TextAlign.center),
          ),
        ),
      );
    }

    final wrongIndices = List<int>.from(_progress['wrong_indices'] ?? []);
    final chunkResults = _progress['chunk_results'] ?? {};
    const chunkSize = 40;

    return Scaffold(
      appBar: AppBar(
        title: const Text("Анатомія", style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_forever, color: Colors.red),
            onPressed: _resetProgress,
          )
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (wrongIndices.isNotEmpty)
            Card(
              color: Colors.purple.shade100,
              child: ListTile(
                leading: const Icon(Icons.warning, color: Colors.purple),
                title: Text("Робота над помилками (${wrongIndices.length})",
                    style: const TextStyle(fontWeight: FontWeight.bold)),
                onTap: () => _startQuiz(context, mode: 'review', wrongIds: wrongIndices),
              ),
            ),
          const SizedBox(height: 10),
          ...List.generate((_questions.length / chunkSize).ceil(), (index) {
            final start = index * chunkSize;
            final end = (start + chunkSize) < _questions.length ? (start + chunkSize) : _questions.length;
            final key = "$start-$end";
            final res = chunkResults[key];
            
            String status = "Не почато";
            IconData icon = Icons.circle_outlined;
            Color color = Colors.grey.shade100;

            if (res != null) {
              final percent = res['percent'];
              status = "${res['score']}/${res['total']} (${percent.toInt()}%)";
              if (percent >= 60) {
                icon = Icons.check_circle;
                color = Colors.green.shade100;
              } else {
                icon = Icons.cancel;
                color = Colors.red.shade100;
              }
            }

            return Card(
              color: color,
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                leading: Icon(icon),
                title: Text("Тест ${index + 1}"),
                subtitle: Text(status),
                onTap: () => _startQuiz(context, mode: 'chunk', start: start, end: end, key: key),
              ),
            );
          }),
        ],
      ),
    );
  }

  void _startQuiz(BuildContext context, {required String mode, int? start, int? end, String? key, List<int>? wrongIds}) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => QuizScreen(
          allQuestions: _questions,
          mode: mode,
          start: start ?? 0,
          end: end ?? 0,
          chunkKey: key,
          wrongIds: wrongIds,
          currentProgress: _progress,
        ),
      ),
    );
    _loadData(); // Оновити дані після повернення
  }
}

// --- ЕКРАН ТЕСТУ ---
class QuizScreen extends StatefulWidget {
  final List<dynamic> allQuestions;
  final String mode;
  final int start;
  final int end;
  final String? chunkKey;
  final List<int>? wrongIds;
  final Map<String, dynamic> currentProgress;

  const QuizScreen({
    super.key,
    required this.allQuestions,
    required this.mode,
    required this.start,
    required this.end,
    this.chunkKey,
    this.wrongIds,
    required this.currentProgress,
  });

  @override
  State<QuizScreen> createState() => _QuizScreenState();
}

class _QuizScreenState extends State<QuizScreen> {
  List<dynamic> _quizQuestions = [];
  int _currentIndex = 0;
  int _score = 0;
  List<int> _newWrongs = [];
  List<int> _correctIds = [];
  bool _answered = false;
  int? _selectedOption;

  @override
  void initState() {
    super.initState();
    if (widget.mode == 'chunk') {
      _quizQuestions = widget.allQuestions.sublist(widget.start, widget.end);
    } else {
      _quizQuestions = widget.allQuestions.where((q) => widget.wrongIds!.contains(q['id'])).toList();
    }
  }

  void _checkAnswer(int index) {
    setState(() {
      _selectedOption = index;
      _answered = true;
      final q = _quizQuestions[_currentIndex];
      final correct = q['c'];
      final id = q['id'];

      if (index == correct) {
        _score++;
        _correctIds.add(id);
      } else {
        _newWrongs.add(id);
      }
    });
  }

  void _nextQuestion() {
    if (_currentIndex < _quizQuestions.length - 1) {
      setState(() {
        _currentIndex++;
        _answered = false;
        _selectedOption = null;
      });
    } else {
      _finishQuiz();
    }
  }

  Future<void> _finishQuiz() async {
    // Логіка збереження
    final prefs = await SharedPreferences.getInstance();
    
    // Оновлюємо список помилок
    Set<int> wrongSet = Set<int>.from(widget.currentProgress['wrong_indices'] ?? []);
    wrongSet.addAll(_newWrongs);
    wrongSet.removeAll(_correctIds);
    
    widget.currentProgress['wrong_indices'] = wrongSet.toList();

    // Оновлюємо статистику блоку
    if (widget.mode == 'chunk' && widget.chunkKey != null) {
      double percent = (_score / _quizQuestions.length) * 100;
      Map<String, dynamic> chunkRes = widget.currentProgress['chunk_results'] ?? {};
      chunkRes[widget.chunkKey!] = {
        "score": _score,
        "total": _quizQuestions.length,
        "percent": percent
      };
      widget.currentProgress['chunk_results'] = chunkRes;
    }

    await prefs.setString('user_progress', json.encode(widget.currentProgress));

    if (!mounted) return;
    
    // Екран результату
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (context) => ResultScreen(
          score: _score,
          total: _quizQuestions.length,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_quizQuestions.isEmpty) {
      return Scaffold(
        appBar: AppBar(title: const Text("Тест")),
        body: const Center(child: Text("Помилок немає! 🎉")),
      );
    }

    final q = _quizQuestions[_currentIndex];

    return Scaffold(
      appBar: AppBar(
        title: Text("Питання ${_currentIndex + 1}/${_quizQuestions.length}"),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(q['q'], style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 20),
            ...List.generate(q['opts'].length, (index) {
              Color color = Colors.white;
              if (_answered) {
                if (index == q['c']) color = Colors.green.shade200;
                else if (index == _selectedOption) color = Colors.red.shade200;
              }
              
              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: color,
                    padding: const EdgeInsets.all(15),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  onPressed: _answered ? null : () => _checkAnswer(index),
                  child: Text(q['opts'][index], 
                    style: const TextStyle(color: Colors.black, fontSize: 16)),
                ),
              );
            }),
            const Spacer(),
            if (_answered)
              ElevatedButton(
                onPressed: _nextQuestion,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.blue, 
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.all(16)
                ),
                child: const Text("Далі", style: TextStyle(fontSize: 18)),
              )
          ],
        ),
      ),
    );
  }
}

class ResultScreen extends StatelessWidget {
  final int score;
  final int total;

  const ResultScreen({super.key, required this.score, required this.total});

  @override
  Widget build(BuildContext context) {
    double percent = (score / total) * 100;
    bool passed = percent >= 60;

    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(passed ? Icons.check_circle : Icons.cancel, 
                 size: 100, color: passed ? Colors.green : Colors.red),
            const SizedBox(height: 20),
            Text("${percent.toInt()}%", 
                 style: TextStyle(fontSize: 40, fontWeight: FontWeight.bold, color: passed ? Colors.green : Colors.red)),
            Text("Правильно: $score з $total", style: const TextStyle(fontSize: 20)),
            const SizedBox(height: 40),
            ElevatedButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text("В меню"),
            )
          ],
        ),
      ),
    );
  }
}
