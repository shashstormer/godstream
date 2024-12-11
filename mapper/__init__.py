import mapper.map_animes


def add_mappers(app, streamable_cache):
    return mapper.map_animes.add_mapper(app, streamable_cache)
