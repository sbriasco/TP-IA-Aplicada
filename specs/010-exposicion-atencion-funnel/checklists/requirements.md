# Specification Quality Checklist: Exposición, detención, atención estimada y funnel comercial

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-23
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Validación del 2026-10-23. En la primera pasada, FR-003 y FR-007 usaban "exposición" para el hecho y para la etapa. Se reescribió FR-003: el hecho se registra al entrar en la vidriera; la etapa del funnel puede ser menor. Segunda pasada: los 16 ítems pasan.
- No quedan marcadores de aclaración. Los umbrales de 3 segundos para la detención y de 8 segundos para la atención estimada quedaron como supuesto explícito en Assumptions y en FR-004, FR-008 y FR-014, para que se puedan cambiar en `/speckit-clarify` antes de planificar.
- El paso observado se separó a propósito de la métrica ya existente de paso frente al local, para que el ingreso vinculado no quede vacío por definición.
- La atención es una estimación por duración de la detención. No observa la mirada. Ese límite está en FR-008 y en el rótulo que exige FR-014.
