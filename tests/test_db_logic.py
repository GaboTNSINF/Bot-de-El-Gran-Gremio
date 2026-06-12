import asyncio
import database
import os

async def main():
    await database.init_db()

    # Pruebas para personaje
    await database.registrar_personaje(1, "Test", "Humano", "Guerrero", 20, "1.80m", "http")
    char = await database.obtener_personaje(1)
    assert char is not None

    res = await database.actualizar_nivel_personaje(1, 2)
    assert res is True
    char = await database.obtener_personaje(1)
    assert char["nivel"] == 2

    res = await database.editar_datos_personaje(1, "Test2", "Elfo", "Mago", 100, "1.90m", "http2")
    assert res is True
    char = await database.obtener_personaje(1)
    assert char["char_name"] == "Test2"

    res = await database.eliminar_personaje(1)
    assert res is True
    char = await database.obtener_personaje(1)
    assert char is None

    # Error cases
    res = await database.actualizar_nivel_personaje(99, 2)
    assert res is False
    res = await database.editar_datos_personaje(99, "T", "E", "M", 10, "1m", "h")
    assert res is False
    res = await database.eliminar_personaje(99)
    assert res is False


    # Pruebas para matchmaking
    await database.guardar_registro_matchmaking(1, "jugador", "1", "Lunes", 0, 100)
    res = await database.eliminar_de_cola(1)
    assert res is True
    res = await database.eliminar_de_cola(99)
    assert res is False

    print("Tests passed")

asyncio.run(main())
