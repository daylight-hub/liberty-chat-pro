from pythonforandroid.recipes.freetype import FreetypeRecipe as _Base


class FreetypeRecipe(_Base):
    # Savannah mirror is intermittently 502. Use the SourceForge mirror,
    # which hosts the same official release tarballs.
    url = "https://downloads.sourceforge.net/project/freetype/freetype2/{version}/freetype-{version}.tar.gz"


recipe = FreetypeRecipe()
