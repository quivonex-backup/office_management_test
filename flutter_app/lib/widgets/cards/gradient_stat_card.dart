import 'package:flutter/material.dart';

/// Big gradient number card of the dashboard (label, value, small subtitle, soft circle in the corner).
class GradientStatCard extends StatelessWidget {
  final String label, value, subtitle;
  final IconData subtitleIcon;
  final List<Color> colors;
  final VoidCallback? onTap;
  const GradientStatCard({
    super.key,
    required this.label,
    required this.value,
    required this.subtitle,
    required this.subtitleIcon,
    required this.colors,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: onTap,
        child: Ink(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            gradient: LinearGradient(colors: colors, begin: Alignment.topLeft, end: Alignment.bottomRight),
            boxShadow: [BoxShadow(color: colors.last.withValues(alpha: 0.25), blurRadius: 14, offset: const Offset(0, 6))],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(20),
            child: Stack(children: [
              Positioned(
                right: -18,
                bottom: -22,
                child: Container(
                  width: 84,
                  height: 84,
                  decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.18), shape: BoxShape.circle),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 14, 14, 14),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                  Row(children: [
                    Expanded(child: Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500))),
                    Icon(onTap != null ? Icons.chevron_right : Icons.more_horiz, color: Colors.white, size: 20),
                  ]),
                  const SizedBox(height: 4),
                  FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Text(value, style: const TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.w700)),
                  ),
                  const SizedBox(height: 6),
                  Row(children: [
                    Icon(subtitleIcon, color: Colors.white70, size: 13),
                    const SizedBox(width: 5),
                    Expanded(child: Text(subtitle, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white70, fontSize: 11.5))),
                  ]),
                ]),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}
