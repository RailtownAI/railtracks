"""Relational persistence for railtracks sessions.

Backs `Session` with a workspace-wide SQLite database at
`<railtracks_home>/data/railtracks.db`. Models, migrations, and the
write-side repository live in this package.
"""
