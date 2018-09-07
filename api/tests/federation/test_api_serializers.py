from funkwhale_api.federation import api_serializers
from funkwhale_api.federation import serializers


def test_library_serializer(factories):
    library = factories["music.Library"](files_count=5678)
    expected = {
        "fid": library.fid,
        "uuid": str(library.uuid),
        "actor": serializers.APIActorSerializer(library.actor).data,
        "name": library.name,
        "description": library.description,
        "creation_date": library.creation_date.isoformat().split("+")[0] + "Z",
        "files_count": library.files_count,
        "privacy_level": library.privacy_level,
        "follow": None,
    }

    serializer = api_serializers.LibrarySerializer(library)

    assert serializer.data == expected


def test_library_serializer_with_follow(factories):
    library = factories["music.Library"](files_count=5678)
    follow = factories["federation.LibraryFollow"](target=library)

    setattr(library, "_follows", [follow])
    expected = {
        "fid": library.fid,
        "uuid": str(library.uuid),
        "actor": serializers.APIActorSerializer(library.actor).data,
        "name": library.name,
        "description": library.description,
        "creation_date": library.creation_date.isoformat().split("+")[0] + "Z",
        "files_count": library.files_count,
        "privacy_level": library.privacy_level,
        "follow": api_serializers.NestedLibraryFollowSerializer(follow).data,
    }

    serializer = api_serializers.LibrarySerializer(library)

    assert serializer.data == expected


def test_library_serializer_validates_existing_follow(factories):
    follow = factories["federation.LibraryFollow"]()
    serializer = api_serializers.LibraryFollowSerializer(
        data={"target": follow.target.uuid}, context={"actor": follow.actor}
    )

    assert serializer.is_valid() is False
    assert "target" in serializer.errors