"""C7.3 — capa de PUBLICACIÓN: del release sellado a artefactos de consumo.

Separada del runner a propósito. El runner produce y sella; esta capa traduce, y sólo puede escribir
en producción cuando el lifecycle lo permite. Un padecimiento `trained` se compila a staging y NO
aparece en ningún output público.
"""
