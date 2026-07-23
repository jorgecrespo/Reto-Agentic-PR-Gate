from __future__ import annotations

import re


class PatchValidationError(ValueError):
    pass


_PATH_PATTERN = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


def validate_patch_shape(patch: str, allowed_prefixes: tuple[str, ...]) -> tuple[str, ...]:
    if not patch.startswith("diff --git "):
        raise PatchValidationError("El parche debe ser un unified diff.")
    if "GIT binary patch" in patch or "\x00" in patch:
        raise PatchValidationError("El parche no puede contener archivos binarios.")
    paths = tuple(_PATH_PATTERN.findall(patch))
    if not paths:
        raise PatchValidationError("El parche no declara archivos destino.")
    for path in paths:
        if path.startswith("/") or ".." in path.split("/"):
            raise PatchValidationError("El parche contiene una ruta insegura.")
        if not any(path.startswith(prefix) for prefix in allowed_prefixes):
            raise PatchValidationError("El parche modifica una ruta fuera del perfil permitido.")
    return paths
