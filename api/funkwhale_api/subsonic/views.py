import datetime

from django.conf import settings
from django.utils import timezone
from rest_framework import exceptions
from rest_framework import permissions as rest_permissions
from rest_framework import renderers, response, viewsets
from rest_framework.decorators import list_route
from rest_framework.serializers import ValidationError

from funkwhale_api.activity import record
from funkwhale_api.common import preferences
from funkwhale_api.favorites.models import TrackFavorite
from funkwhale_api.music import models as music_models
from funkwhale_api.music import utils
from funkwhale_api.music import views as music_views
from funkwhale_api.playlists import models as playlists_models

from . import authentication, filters, negotiation, serializers


def find_object(
    queryset, model_field="pk", field="id", cast=int, filter_playable=False
):
    def decorator(func):
        def inner(self, request, *args, **kwargs):
            data = request.GET or request.POST
            try:
                raw_value = data[field]
            except KeyError:
                return response.Response(
                    {
                        "error": {
                            "code": 10,
                            "message": "required parameter '{}' not present".format(
                                field
                            ),
                        }
                    }
                )
            try:
                value = cast(raw_value)
            except (ValueError, TypeError, ValidationError):
                return response.Response(
                    {
                        "error": {
                            "code": 0,
                            "message": 'For input string "{}"'.format(raw_value),
                        }
                    }
                )
            qs = queryset
            if hasattr(qs, "__call__"):
                qs = qs(request)

            if filter_playable:
                actor = utils.get_actor_from_request(request)
                qs = qs.playable_by(actor).distinct()

            try:
                obj = qs.get(**{model_field: value})
            except qs.model.DoesNotExist:
                return response.Response(
                    {
                        "error": {
                            "code": 70,
                            "message": "{} not found".format(
                                qs.model.__class__.__name__
                            ),
                        }
                    }
                )
            kwargs["obj"] = obj
            return func(self, request, *args, **kwargs)

        return inner

    return decorator


class SubsonicViewSet(viewsets.GenericViewSet):
    content_negotiation_class = negotiation.SubsonicContentNegociation
    authentication_classes = [authentication.SubsonicAuthentication]
    permissions_classes = [rest_permissions.IsAuthenticated]

    def dispatch(self, request, *args, **kwargs):
        if not preferences.get("subsonic__enabled"):
            r = response.Response({}, status=405)
            r.accepted_renderer = renderers.JSONRenderer()
            r.accepted_media_type = "application/json"
            r.renderer_context = {}
            return r
        return super().dispatch(request, *args, **kwargs)

    def handle_exception(self, exc):
        # subsonic API sends 200 status code with custom error
        # codes in the payload
        mapping = {exceptions.AuthenticationFailed: (40, "Wrong username or password.")}
        payload = {"status": "failed"}
        if exc.__class__ in mapping:
            code, message = mapping[exc.__class__]
        else:
            return super().handle_exception(exc)
        payload["error"] = {"code": code, "message": message}

        return response.Response(payload, status=200)

    @list_route(methods=["get", "post"], permission_classes=[])
    def ping(self, request, *args, **kwargs):
        data = {"status": "ok", "version": "1.16.0"}
        return response.Response(data, status=200)

    @list_route(
        methods=["get", "post"],
        url_name="get_license",
        permissions_classes=[],
        url_path="getLicense",
    )
    def get_license(self, request, *args, **kwargs):
        now = timezone.now()
        data = {
            "status": "ok",
            "version": "1.16.0",
            "license": {
                "valid": "true",
                "email": "valid@valid.license",
                "licenseExpires": now + datetime.timedelta(days=365),
            },
        }
        return response.Response(data, status=200)

    @list_route(methods=["get", "post"], url_name="get_artists", url_path="getArtists")
    def get_artists(self, request, *args, **kwargs):
        artists = music_models.Artist.objects.all().playable_by(
            utils.get_actor_from_request(request)
        )
        data = serializers.GetArtistsSerializer(artists).data
        payload = {"artists": data}

        return response.Response(payload, status=200)

    @list_route(methods=["get", "post"], url_name="get_indexes", url_path="getIndexes")
    def get_indexes(self, request, *args, **kwargs):
        artists = music_models.Artist.objects.all().playable_by(
            utils.get_actor_from_request(request)
        )
        data = serializers.GetArtistsSerializer(artists).data
        payload = {"indexes": data}

        return response.Response(payload, status=200)

    @list_route(methods=["get", "post"], url_name="get_artist", url_path="getArtist")
    @find_object(music_models.Artist.objects.all(), filter_playable=True)
    def get_artist(self, request, *args, **kwargs):
        artist = kwargs.pop("obj")
        data = serializers.GetArtistSerializer(artist).data
        payload = {"artist": data}

        return response.Response(payload, status=200)

    @list_route(methods=["get", "post"], url_name="get_song", url_path="getSong")
    @find_object(music_models.Track.objects.all(), filter_playable=True)
    def get_song(self, request, *args, **kwargs):
        track = kwargs.pop("obj")
        data = serializers.GetSongSerializer(track).data
        payload = {"song": data}

        return response.Response(payload, status=200)

    @list_route(
        methods=["get", "post"], url_name="get_artist_info2", url_path="getArtistInfo2"
    )
    @find_object(music_models.Artist.objects.all(), filter_playable=True)
    def get_artist_info2(self, request, *args, **kwargs):
        payload = {"artist-info2": {}}

        return response.Response(payload, status=200)

    @list_route(methods=["get", "post"], url_name="get_album", url_path="getAlbum")
    @find_object(
        music_models.Album.objects.select_related("artist"), filter_playable=True
    )
    def get_album(self, request, *args, **kwargs):
        album = kwargs.pop("obj")
        data = serializers.GetAlbumSerializer(album).data
        payload = {"album": data}
        return response.Response(payload, status=200)

    @list_route(methods=["get", "post"], url_name="stream", url_path="stream")
    @find_object(music_models.Track.objects.all(), filter_playable=True)
    def stream(self, request, *args, **kwargs):
        track = kwargs.pop("obj")
        queryset = track.uploads.select_related("track__album__artist", "track__artist")
        upload = queryset.first()
        if not upload:
            return response.Response(status=404)
        return music_views.handle_serve(upload=upload, user=request.user)

    @list_route(methods=["get", "post"], url_name="star", url_path="star")
    @find_object(music_models.Track.objects.all())
    def star(self, request, *args, **kwargs):
        track = kwargs.pop("obj")
        TrackFavorite.add(user=request.user, track=track)
        return response.Response({"status": "ok"})

    @list_route(methods=["get", "post"], url_name="unstar", url_path="unstar")
    @find_object(music_models.Track.objects.all())
    def unstar(self, request, *args, **kwargs):
        track = kwargs.pop("obj")
        request.user.track_favorites.filter(track=track).delete()
        return response.Response({"status": "ok"})

    @list_route(
        methods=["get", "post"], url_name="get_starred2", url_path="getStarred2"
    )
    def get_starred2(self, request, *args, **kwargs):
        favorites = request.user.track_favorites.all()
        data = {"starred2": {"song": serializers.get_starred_tracks_data(favorites)}}
        return response.Response(data)

    @list_route(methods=["get", "post"], url_name="get_starred", url_path="getStarred")
    def get_starred(self, request, *args, **kwargs):
        favorites = request.user.track_favorites.all()
        data = {"starred": {"song": serializers.get_starred_tracks_data(favorites)}}
        return response.Response(data)

    @list_route(
        methods=["get", "post"], url_name="get_album_list2", url_path="getAlbumList2"
    )
    def get_album_list2(self, request, *args, **kwargs):
        queryset = music_models.Album.objects.with_tracks_count().order_by(
            "artist__name"
        )
        data = request.GET or request.POST
        filterset = filters.AlbumList2FilterSet(data, queryset=queryset)
        queryset = filterset.qs
        actor = utils.get_actor_from_request(request)
        queryset = queryset.playable_by(actor)

        try:
            offset = int(data["offset"])
        except (TypeError, KeyError, ValueError):
            offset = 0

        try:
            size = int(data["size"])
        except (TypeError, KeyError, ValueError):
            size = 50

        size = min(size, 500)
        queryset = queryset[offset : offset + size]
        data = {"albumList2": {"album": serializers.get_album_list2_data(queryset)}}
        return response.Response(data)

    @list_route(methods=["get", "post"], url_name="search3", url_path="search3")
    def search3(self, request, *args, **kwargs):
        data = request.GET or request.POST
        query = str(data.get("query", "")).replace("*", "")
        actor = utils.get_actor_from_request(request)
        conf = [
            {
                "subsonic": "artist",
                "search_fields": ["name"],
                "queryset": (
                    music_models.Artist.objects.with_albums_count().values(
                        "id", "_albums_count", "name"
                    )
                ),
                "serializer": lambda qs: [serializers.get_artist_data(a) for a in qs],
            },
            {
                "subsonic": "album",
                "search_fields": ["title"],
                "queryset": (
                    music_models.Album.objects.with_tracks_count().select_related(
                        "artist"
                    )
                ),
                "serializer": serializers.get_album_list2_data,
            },
            {
                "subsonic": "song",
                "search_fields": ["title"],
                "queryset": (
                    music_models.Track.objects.prefetch_related(
                        "uploads"
                    ).select_related("album__artist")
                ),
                "serializer": serializers.get_song_list_data,
            },
        ]
        payload = {"searchResult3": {}}
        for c in conf:
            offsetKey = "{}Offset".format(c["subsonic"])
            countKey = "{}Count".format(c["subsonic"])
            try:
                offset = int(data[offsetKey])
            except (TypeError, KeyError, ValueError):
                offset = 0

            try:
                size = int(data[countKey])
            except (TypeError, KeyError, ValueError):
                size = 20

            size = min(size, 100)
            queryset = c["queryset"]
            if query:
                queryset = c["queryset"].filter(
                    utils.get_query(query, c["search_fields"])
                )
            queryset = queryset.playable_by(actor)
            queryset = queryset[offset : offset + size]
            payload["searchResult3"][c["subsonic"]] = c["serializer"](queryset)
        return response.Response(payload)

    @list_route(
        methods=["get", "post"], url_name="get_playlists", url_path="getPlaylists"
    )
    def get_playlists(self, request, *args, **kwargs):
        playlists = request.user.playlists.with_tracks_count().select_related("user")
        data = {
            "playlists": {
                "playlist": [serializers.get_playlist_data(p) for p in playlists]
            }
        }
        return response.Response(data)

    @list_route(
        methods=["get", "post"], url_name="get_playlist", url_path="getPlaylist"
    )
    @find_object(playlists_models.Playlist.objects.with_tracks_count())
    def get_playlist(self, request, *args, **kwargs):
        playlist = kwargs.pop("obj")
        data = {"playlist": serializers.get_playlist_detail_data(playlist)}
        return response.Response(data)

    @list_route(
        methods=["get", "post"], url_name="update_playlist", url_path="updatePlaylist"
    )
    @find_object(lambda request: request.user.playlists.all(), field="playlistId")
    def update_playlist(self, request, *args, **kwargs):
        playlist = kwargs.pop("obj")
        data = request.GET or request.POST
        new_name = data.get("name", "")
        if new_name:
            playlist.name = new_name
            playlist.save(update_fields=["name", "modification_date"])
        try:
            to_remove = int(data["songIndexToRemove"])
            plt = playlist.playlist_tracks.get(index=to_remove)
        except (TypeError, ValueError, KeyError):
            pass
        except playlists_models.PlaylistTrack.DoesNotExist:
            pass
        else:
            plt.delete(update_indexes=True)

        ids = []
        for i in data.getlist("songIdToAdd"):
            try:
                ids.append(int(i))
            except (TypeError, ValueError):
                pass
        if ids:
            tracks = music_models.Track.objects.filter(pk__in=ids)
            by_id = {t.id: t for t in tracks}
            sorted_tracks = []
            for i in ids:
                try:
                    sorted_tracks.append(by_id[i])
                except KeyError:
                    pass
            if sorted_tracks:
                playlist.insert_many(sorted_tracks)

        data = {"status": "ok"}
        return response.Response(data)

    @list_route(
        methods=["get", "post"], url_name="delete_playlist", url_path="deletePlaylist"
    )
    @find_object(lambda request: request.user.playlists.all())
    def delete_playlist(self, request, *args, **kwargs):
        playlist = kwargs.pop("obj")
        playlist.delete()
        data = {"status": "ok"}
        return response.Response(data)

    @list_route(
        methods=["get", "post"], url_name="create_playlist", url_path="createPlaylist"
    )
    def create_playlist(self, request, *args, **kwargs):
        data = request.GET or request.POST
        name = data.get("name", "")
        if not name:
            return response.Response(
                {
                    "error": {
                        "code": 10,
                        "message": "Playlist ID or name must be specified.",
                    }
                }
            )

        playlist = request.user.playlists.create(name=name)
        ids = []
        for i in data.getlist("songId"):
            try:
                ids.append(int(i))
            except (TypeError, ValueError):
                pass

        if ids:
            tracks = music_models.Track.objects.filter(pk__in=ids)
            by_id = {t.id: t for t in tracks}
            sorted_tracks = []
            for i in ids:
                try:
                    sorted_tracks.append(by_id[i])
                except KeyError:
                    pass
            if sorted_tracks:
                playlist.insert_many(sorted_tracks)
        playlist = request.user.playlists.with_tracks_count().get(pk=playlist.pk)
        data = {"playlist": serializers.get_playlist_detail_data(playlist)}
        return response.Response(data)

    @list_route(
        methods=["get", "post"],
        url_name="get_music_folders",
        url_path="getMusicFolders",
    )
    def get_music_folders(self, request, *args, **kwargs):
        data = {"musicFolders": {"musicFolder": [{"id": 1, "name": "Music"}]}}
        return response.Response(data)

    @list_route(
        methods=["get", "post"], url_name="get_cover_art", url_path="getCoverArt"
    )
    def get_cover_art(self, request, *args, **kwargs):
        data = request.GET or request.POST
        id = data.get("id", "")
        if not id:
            return response.Response(
                {"error": {"code": 10, "message": "cover art ID must be specified."}}
            )

        if id.startswith("al-"):
            try:
                album_id = int(id.replace("al-", ""))
                album = (
                    music_models.Album.objects.exclude(cover__isnull=True)
                    .exclude(cover="")
                    .get(pk=album_id)
                )
            except (TypeError, ValueError, music_models.Album.DoesNotExist):
                return response.Response(
                    {"error": {"code": 70, "message": "cover art not found."}}
                )
            cover = album.cover
        else:
            return response.Response(
                {"error": {"code": 70, "message": "cover art not found."}}
            )

        mapping = {"nginx": "X-Accel-Redirect", "apache2": "X-Sendfile"}
        path = music_views.get_file_path(cover)
        file_header = mapping[settings.REVERSE_PROXY_TYPE]
        # let the proxy set the content-type
        r = response.Response({}, content_type="")
        r[file_header] = path
        return r

    @list_route(methods=["get", "post"], url_name="scrobble", url_path="scrobble")
    def scrobble(self, request, *args, **kwargs):
        data = request.GET or request.POST
        serializer = serializers.ScrobbleSerializer(
            data=data, context={"user": request.user}
        )
        if not serializer.is_valid():
            return response.Response(
                {"error": {"code": 0, "message": "Invalid payload"}}
            )
        if serializer.validated_data["submission"]:
            listening = serializer.save()
            record.send(listening)
        return response.Response({})
