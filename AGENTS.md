This rules should be followed in every single line of code.

# The sacred code commandments:

1. Never add markdown files unless explicitly requested.
2. Never use useEffect in the frontend unless you really think it's the better option, explain why and request approval.
3. Always add types to python code. Use built-in types when available.
4. Do not use jsonify in the backend.
5. Never add fallbacks.
6. Never add comments related to fixed or changes, comments should be related to the code not the edits.
7. Never add backwards compatibility, we are developing a new product.
8. Keep error handling simple.
9. Assume parameters will be passed correctly, if a function is supposed to get an string don't validate it.
10. Never add features the user didn't explicitly ask for.
11. Frontend logic and frontend views should be separated, components must be dumb and only receive props while the logic remains in the hooks.
12. One file, one component.
13. Before creating a component check if we already have one with the same functionality.
14. Before you finish a feature, review that it meets all of the commandments.
15. Never use optional chaining (?.) or null checks for guaranteed APIs and interfaces.
16. If you previously created something or made some changes that are no longer needed, remove them.
17. When adding text always use i18n, and only add support for spanish.
18. When interfaces require loading always add skeleton components.
19. Frontend files are not allowed to have more than 800 lines of code. Ideally, they should have less than 500 lines of code. If files get too large, refactor them.
20. All frontend API requests should use centralized base fetch in client.ts.
21. If you see code that's unused or no longer needed, remove it.
22. When modifying SQL function signatures (renaming, changing parameters) or removing SQL functions from the codebase, remind the user to DROP the old function in the database. The database schema and functions goes in the database folder.
23. App.tsx is a wiring-only file. It must not contain logic, callbacks, or data transformations. All logic must live in hooks; App.tsx only passes dependencies and renders components.
24. All modals must use the Dialog component from `@/components/ui/dialog`. They must have: X close button, Escape to close, and when they have an action, a Cancel button alongside the action button.
25. Environment variables must be loaded with os.environ[] so that the app fails if a variable is missing.
26. All API errors must be shown to the user via toast notifications.
27. Backend CRUD and important actions must be logged. Use human-readable identifiers (names) when already available. Never make extra DB queries just for logging. Use a prefix tag like `[MODULE]` for context.
28. All delete buttons must use the HoldButton component (hold to delete pattern).
29. Never run SQL or any write/DDL/data migration against the database yourself (no MCP writes, scripts, psql, or client calls). Only run read-only queries to investigate. For any change, write a migration script and hand it to the user to validate and run themselves.
30. Migration scripts are temporary: never commit them. Once the user has run a migration, delete the script. The canonical schema in the database folder is the only SQL that lives in the repo.
31. Never use browser tools or open, control, or automate a browser for any reason.
32. Never version cache keys to invalidate cached data. When a change affects a cache, explicitly delete or invalidate the affected cache entries.
33. When I point out a problem, treat my message as an instruction to address it within the task's scope. I want corrective action and verified results, not apologies, excuses, or acknowledgments in place of doing the work.

# The code is the documentation

There is no separate documentation: the code is the documentation and the source of truth.

Before making changes, read and analyze the relevant code, its callers, dependencies, and comparable implementations. Trace how the behavior works through the actual application, including the conditions and state that control it. Do not assume that a name, parameter, or isolated component tells the whole story. Follow established patterns and check every assumption against the code before acting.