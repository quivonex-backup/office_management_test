import 'package:flutter/material.dart';

class PaginationBar extends StatelessWidget {
  final int page, totalPages, totalRows;
  final void Function(int page) onPage;

  /// Optional rows-per-page selector (shown when [onPageSize] is given).
  final int? pageSize;
  final void Function(int size)? onPageSize;
  final List<int> sizes;
  const PaginationBar({
    super.key,
    required this.page,
    required this.totalPages,
    required this.totalRows,
    required this.onPage,
    this.pageSize,
    this.onPageSize,
    this.sizes = const [10, 25, 50, 100],
  });

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Wrap(alignment: WrapAlignment.center, crossAxisAlignment: WrapCrossAlignment.center, children: [
          if (onPageSize != null && pageSize != null) ...[
            const Text('Rows per page '),
            DropdownButton<int>(
              value: sizes.contains(pageSize) ? pageSize : null,
              underline: const SizedBox.shrink(),
              items: [for (final n in sizes) DropdownMenuItem(value: n, child: Text('$n'))],
              onChanged: (v) => v == null ? null : onPageSize!(v),
            ),
            const SizedBox(width: 12),
          ],
          IconButton(onPressed: page > 1 ? () => onPage(page - 1) : null, icon: const Icon(Icons.chevron_left)),
          Text('Page $page of ${totalPages < 1 ? 1 : totalPages}  ·  $totalRows rows'),
          IconButton(onPressed: page < totalPages ? () => onPage(page + 1) : null, icon: const Icon(Icons.chevron_right)),
        ]),
      );
}
