"""Convex-backed storage for hosted and self-hosted deployments."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

from openpasture.domain import (
    Animal,
    DailyBrief,
    DataPipeline,
    Farm,
    FarmActivityAttachment,
    FarmActivityEvent,
    FarmActivityTarget,
    FarmerAction,
    GeoFeature,
    GeoPoint,
    GeoPolygon,
    Herd,
    LandUnit,
    MovementDecision,
    Observation,
    WaterSource,
)


def _compact(value: dict[str, object]) -> dict[str, object]:
    return {key: item for key, item in value.items() if item is not None}


def _datetime_to_text(value: datetime) -> str:
    return value.isoformat()


def _date_to_text(value: date) -> str:
    return value.isoformat()


def _datetime_from_text(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _date_from_text(value: str) -> date:
    return date.fromisoformat(value)


def _normalize_convex_site_url(deployment_url: str) -> str:
    parsed = urlparse(deployment_url.rstrip("/"))
    hostname = parsed.hostname or ""
    if hostname.endswith(".convex.cloud"):
        hostname = hostname.removesuffix(".convex.cloud") + ".convex.site"
        netloc = hostname if parsed.port is None else f"{hostname}:{parsed.port}"
        parsed = parsed._replace(netloc=netloc)
    return urlunparse(parsed).rstrip("/")


def _point(value: object) -> GeoPoint | None:
    return GeoPoint.from_geojson(value) if isinstance(value, dict) else None


def _feature(value: object) -> GeoFeature:
    if not isinstance(value, dict):
        raise ValueError("Convex land-unit record is missing geometry.")
    return GeoFeature.from_geojson(value)


def _boundary(value: object) -> GeoFeature | None:
    return GeoFeature.from_geojson(value) if isinstance(value, dict) else None


def _water_sources(values: object) -> list[WaterSource]:
    if not isinstance(values, list):
        return []
    sources: list[WaterSource] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        source_id = item.get("id")
        name = item.get("name")
        if not isinstance(source_id, str) or not isinstance(name, str):
            continue
        sources.append(
            WaterSource(
                id=source_id,
                name=name,
                location=_point(item.get("location")),
                notes=str(item.get("notes") or ""),
            )
        )
    return sources


def _serialize_water_sources(values: list[WaterSource]) -> list[dict[str, object]]:
    return [
        {
            "id": source.id,
            "name": source.name,
            "location": source.location.to_geojson() if source.location else None,
            "notes": source.notes,
        }
        for source in values
    ]


class ConvexStore:
    """HTTP-backed implementation of the FarmStore protocol."""

    def __init__(self, deployment_url: str, deploy_key: str | None = None):
        self.deployment_url = _normalize_convex_site_url(deployment_url)
        self.deploy_key = deploy_key
        self.store_url = urljoin(f"{self.deployment_url}/", "store")
        self.media_import_url = urljoin(f"{self.deployment_url}/", "media/import")

    def connect(self) -> None:
        """Validate configuration for the remote Convex deployment."""
        if not self.deployment_url.strip():
            raise ValueError("Convex deployment URL is required.")
        if not self.deploy_key:
            raise ValueError("Convex runtime key is required.")

    def _request(self, operation: str, args: dict[str, object] | None = None) -> object:
        self.connect()
        response = httpx.post(
            self.store_url,
            json={"operation": operation, "args": args or {}},
            headers={"authorization": f"Bearer {self.deploy_key}"},
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(str(payload.get("error") or "Convex store request failed."))
        return payload.get("result")

    def import_media_from_url(
        self,
        download_url: str,
        *,
        farm_id: str,
        file_id: object | None = None,
        file_name: object | None = None,
        content_type: object | None = None,
    ) -> dict[str, object]:
        """Copy a temporary hosted file URL into durable OpenPasture media storage."""

        self.connect()
        response = httpx.post(
            self.media_import_url,
            json=_compact(
                {
                    "downloadUrl": download_url,
                    "farmId": farm_id,
                    "fileId": file_id if isinstance(file_id, str) else None,
                    "fileName": file_name if isinstance(file_name, str) else None,
                    "contentType": content_type if isinstance(content_type, str) else None,
                }
            ),
            headers={"authorization": f"Bearer {self.deploy_key}"},
            timeout=45.0,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            if response.status_code == 404:
                return {"url": download_url, "metadata": {"media_import": "unsupported"}}
            raise
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(str(payload.get("error") or "Convex media import failed."))
        result = payload.get("result")
        return result if isinstance(result, dict) else {}

    def _farm_record(self, farm: Farm) -> dict[str, object]:
        return _compact(
            {
                "farmId": farm.id,
                "name": farm.name,
                "timezone": farm.timezone,
                "boundary": farm.boundary.to_geojson() if farm.boundary else None,
                "location": farm.location.to_geojson() if farm.location else None,
                "herdIds": farm.herd_ids,
                "waterSources": _serialize_water_sources(farm.water_sources),
                "notes": farm.notes,
                "createdAt": _datetime_to_text(farm.created_at),
            }
        )

    def _farm_from_record(self, record: object) -> Farm | None:
        if not isinstance(record, dict):
            return None
        return Farm(
            id=str(record["farmId"]),
            name=str(record["name"]),
            timezone=str(record["timezone"]),
            boundary=_boundary(record.get("boundary")),
            location=_point(record.get("location")),
            herd_ids=[str(item) for item in record.get("herdIds", [])],
            water_sources=_water_sources(record.get("waterSources")),
            notes=str(record.get("notes") or ""),
            created_at=_datetime_from_text(str(record["createdAt"])),
        )

    def _land_unit_record(self, land_unit: LandUnit) -> dict[str, object]:
        return _compact(
            {
                "landUnitId": land_unit.id,
                "farmId": land_unit.farm_id,
                "parentId": land_unit.parent_id,
                "unitType": land_unit.unit_type,
                "name": land_unit.name,
                "geometry": land_unit.geometry.to_geojson(),
                "areaHectares": land_unit.area_hectares,
                "confidence": land_unit.confidence,
                "provenance": land_unit.provenance,
                "geometryVersion": land_unit.geometry_version,
                "status": land_unit.status,
                "notes": land_unit.notes,
                "warnings": land_unit.warnings,
                "createdAt": _datetime_to_text(land_unit.created_at),
                "updatedAt": _datetime_to_text(land_unit.updated_at),
            }
        )

    def _land_unit_from_record(self, record: object) -> LandUnit | None:
        if not isinstance(record, dict):
            return None
        return LandUnit(
            id=str(record["landUnitId"]),
            farm_id=str(record["farmId"]),
            parent_id=record.get("parentId") if isinstance(record.get("parentId"), str) else None,
            unit_type=str(record["unitType"]),
            name=str(record["name"]),
            geometry=_feature(record.get("geometry")),
            area_hectares=record.get("areaHectares") if isinstance(record.get("areaHectares"), (int, float)) else None,
            confidence=float(record.get("confidence") or 1.0),
            provenance=record.get("provenance") if isinstance(record.get("provenance"), dict) else {},
            geometry_version=int(record.get("geometryVersion") or 1),
            status=str(record.get("status") or "draft"),
            notes=str(record.get("notes") or ""),
            warnings=[str(item) for item in record.get("warnings", [])],
            created_at=_datetime_from_text(str(record["createdAt"])),
            updated_at=_datetime_from_text(str(record["updatedAt"])),
        )

    def _herd_record(self, herd: Herd) -> dict[str, object]:
        return _compact(
            {
                "herdId": herd.id,
                "farmId": herd.farm_id,
                "species": herd.species,
                "count": herd.count,
                "currentPaddockId": herd.current_paddock_id,
                "animalUnits": herd.animal_units,
                "notes": herd.notes,
            }
        )

    def _herd_from_record(self, record: object) -> Herd | None:
        if not isinstance(record, dict):
            return None
        return Herd(
            id=str(record["herdId"]),
            farm_id=str(record["farmId"]),
            species=str(record["species"]),
            count=int(record["count"]),
            current_paddock_id=record.get("currentPaddockId") if isinstance(record.get("currentPaddockId"), str) else None,
            animal_units=record.get("animalUnits") if isinstance(record.get("animalUnits"), (int, float)) else None,
            notes=str(record.get("notes") or ""),
        )

    def _animal_record(self, animal: Animal) -> dict[str, object]:
        return _compact(
            {
                "animalId": animal.id,
                "farmId": animal.farm_id,
                "herdId": animal.herd_id,
                "species": animal.species,
                "sex": animal.sex,
                "name": animal.name,
                "tag": animal.tag,
                "secondaryTags": animal.secondary_tags,
                "breed": animal.breed,
                "birthDate": animal.birth_date,
                "damId": animal.dam_id,
                "sireId": animal.sire_id,
                "status": animal.status,
                "currentPaddockId": animal.current_paddock_id,
                "notes": animal.notes,
                "metadata": animal.metadata,
                "createdAt": _datetime_to_text(animal.created_at),
                "updatedAt": _datetime_to_text(animal.updated_at),
            }
        )

    def _animal_from_record(self, record: object) -> Animal | None:
        if not isinstance(record, dict):
            return None
        return Animal(
            id=str(record["animalId"]),
            farm_id=str(record["farmId"]),
            herd_id=record.get("herdId") if isinstance(record.get("herdId"), str) else None,
            species=str(record["species"]),
            sex=str(record["sex"]),
            name=record.get("name") if isinstance(record.get("name"), str) else None,
            tag=str(record["tag"]),
            secondary_tags=[str(item) for item in record.get("secondaryTags", [])],
            breed=record.get("breed") if isinstance(record.get("breed"), str) else None,
            birth_date=record.get("birthDate") if isinstance(record.get("birthDate"), str) else None,
            dam_id=record.get("damId") if isinstance(record.get("damId"), str) else None,
            sire_id=record.get("sireId") if isinstance(record.get("sireId"), str) else None,
            status=str(record.get("status") or "active"),
            current_paddock_id=record.get("currentPaddockId") if isinstance(record.get("currentPaddockId"), str) else None,
            notes=str(record.get("notes") or ""),
            metadata=record.get("metadata") if isinstance(record.get("metadata"), dict) else {},
            created_at=_datetime_from_text(str(record["createdAt"])),
            updated_at=_datetime_from_text(str(record["updatedAt"])),
        )

    def _observation_record(self, observation: Observation) -> dict[str, object]:
        return _compact(
            {
                "observationId": observation.id,
                "farmId": observation.farm_id,
                "source": observation.source,
                "observedAt": _datetime_to_text(observation.observed_at),
                "content": observation.content,
                "paddockId": observation.paddock_id,
                "herdId": observation.herd_id,
                "metrics": observation.metrics,
                "mediaUrl": observation.media_url,
                "mediaThumbnailUrl": observation.media_thumbnail_url,
                "mediaMetadata": observation.media_metadata,
                "tags": observation.tags,
            }
        )

    def _observation_from_record(self, record: object) -> Observation | None:
        if not isinstance(record, dict):
            return None
        return Observation(
            id=str(record["observationId"]),
            farm_id=str(record["farmId"]),
            source=str(record["source"]),
            observed_at=_datetime_from_text(str(record["observedAt"])),
            content=str(record["content"]),
            paddock_id=record.get("paddockId") if isinstance(record.get("paddockId"), str) else None,
            herd_id=record.get("herdId") if isinstance(record.get("herdId"), str) else None,
            metrics=record.get("metrics") if isinstance(record.get("metrics"), dict) else {},
            media_url=record.get("mediaUrl") if isinstance(record.get("mediaUrl"), str) else None,
            media_thumbnail_url=(
                record.get("mediaThumbnailUrl") if isinstance(record.get("mediaThumbnailUrl"), str) else None
            ),
            media_metadata=record.get("mediaMetadata") if isinstance(record.get("mediaMetadata"), dict) else {},
            tags=[str(item) for item in record.get("tags", [])],
        )

    def _activity_record(self, event: FarmActivityEvent) -> dict[str, object]:
        return _compact(
            {
                "activityId": event.id,
                "farmId": event.farm_id,
                "eventType": event.event_type,
                "source": event.source,
                "occurredAt": _datetime_to_text(event.occurred_at),
                "recordedAt": _datetime_to_text(event.recorded_at),
                "title": event.title,
                "body": event.body,
                "summary": event.summary,
                "payload": event.payload,
                "provenance": event.provenance,
                "visibility": event.visibility,
                "targets": [
                    {
                        "subjectType": target.subject_type,
                        "subjectId": target.subject_id,
                        "relationship": target.relationship,
                    }
                    for target in event.targets
                ],
                "attachments": [
                    _compact(
                        {
                            "attachmentId": attachment.id,
                            "url": attachment.url,
                            "mediaType": attachment.media_type,
                            "thumbnailUrl": attachment.thumbnail_url,
                            "fileName": attachment.file_name,
                            "contentType": attachment.content_type,
                            "metadata": attachment.metadata,
                        }
                    )
                    for attachment in event.attachments
                ],
            }
        )

    def _activity_from_record(self, record: object) -> FarmActivityEvent | None:
        if not isinstance(record, dict):
            return None
        return FarmActivityEvent(
            id=str(record["activityId"]),
            farm_id=str(record["farmId"]),
            event_type=str(record["eventType"]),
            source=str(record["source"]),
            occurred_at=_datetime_from_text(str(record["occurredAt"])),
            recorded_at=_datetime_from_text(str(record["recordedAt"])),
            title=str(record["title"]),
            body=str(record.get("body") or ""),
            summary=record.get("summary") if isinstance(record.get("summary"), str) else None,
            payload=record.get("payload") if isinstance(record.get("payload"), dict) else {},
            provenance=record.get("provenance") if isinstance(record.get("provenance"), dict) else {},
            visibility=str(record.get("visibility") or "farm"),
            targets=[
                FarmActivityTarget(
                    subject_type=str(target["subjectType"]),
                    subject_id=str(target["subjectId"]),
                    relationship=str(target.get("relationship") or "primary"),
                )
                for target in record.get("targets", [])
                if isinstance(target, dict)
            ],
            attachments=[
                FarmActivityAttachment(
                    id=str(attachment["attachmentId"]),
                    url=str(attachment["url"]),
                    media_type=str(attachment["mediaType"]),
                    thumbnail_url=(
                        attachment.get("thumbnailUrl") if isinstance(attachment.get("thumbnailUrl"), str) else None
                    ),
                    file_name=attachment.get("fileName") if isinstance(attachment.get("fileName"), str) else None,
                    content_type=attachment.get("contentType") if isinstance(attachment.get("contentType"), str) else None,
                    metadata=attachment.get("metadata") if isinstance(attachment.get("metadata"), dict) else {},
                )
                for attachment in record.get("attachments", [])
                if isinstance(attachment, dict)
            ],
        )

    def _pipeline_record(self, pipeline: DataPipeline) -> dict[str, object]:
        return _compact(
            {
                "pipelineId": pipeline.id,
                "farmId": pipeline.farm_id,
                "name": pipeline.name,
                "profileId": pipeline.profile_id,
                "loginUrl": pipeline.login_url,
                "targetUrls": pipeline.target_urls,
                "extractionPrompts": pipeline.extraction_prompts,
                "observationSource": pipeline.observation_source,
                "observationTags": pipeline.observation_tags,
                "schedule": pipeline.schedule,
                "vendorSkillVersion": pipeline.vendor_skill_version,
                "enabled": pipeline.enabled,
                "lastCollectedAt": _datetime_to_text(pipeline.last_collected_at) if pipeline.last_collected_at else None,
                "lastError": pipeline.last_error,
                "createdAt": _datetime_to_text(pipeline.created_at),
            }
        )

    def _pipeline_from_record(self, record: object) -> DataPipeline | None:
        if not isinstance(record, dict):
            return None
        return DataPipeline(
            id=str(record["pipelineId"]),
            farm_id=str(record["farmId"]),
            name=str(record["name"]),
            profile_id=str(record["profileId"]),
            login_url=str(record["loginUrl"]),
            target_urls=[str(item) for item in record.get("targetUrls", [])],
            extraction_prompts=[str(item) for item in record.get("extractionPrompts", [])],
            observation_source=str(record["observationSource"]),
            observation_tags=[str(item) for item in record.get("observationTags", [])],
            schedule=str(record.get("schedule") or "0 5 * * *"),
            vendor_skill_version=record.get("vendorSkillVersion") if isinstance(record.get("vendorSkillVersion"), str) else None,
            enabled=bool(record.get("enabled", True)),
            last_collected_at=(
                _datetime_from_text(str(record["lastCollectedAt"]))
                if isinstance(record.get("lastCollectedAt"), str)
                else None
            ),
            last_error=record.get("lastError") if isinstance(record.get("lastError"), str) else None,
            created_at=_datetime_from_text(str(record["createdAt"])),
        )

    def _farmer_action_record(self, action: FarmerAction) -> dict[str, object]:
        return _compact(
            {
                "actionId": action.id,
                "farmId": action.farm_id,
                "actionType": action.action_type,
                "summary": action.summary,
                "context": action.context,
                "createdAt": _datetime_to_text(action.created_at),
                "resolvedAt": _datetime_to_text(action.resolved_at) if action.resolved_at else None,
                "resolution": action.resolution,
            }
        )

    def _farmer_action_from_record(self, record: object) -> FarmerAction | None:
        if not isinstance(record, dict):
            return None
        return FarmerAction(
            id=str(record["actionId"]),
            farm_id=str(record["farmId"]),
            action_type=str(record["actionType"]),
            summary=str(record["summary"]),
            context=record.get("context") if isinstance(record.get("context"), dict) else {},
            created_at=_datetime_from_text(str(record["createdAt"])),
            resolved_at=_datetime_from_text(str(record["resolvedAt"])) if isinstance(record.get("resolvedAt"), str) else None,
            resolution=record.get("resolution") if isinstance(record.get("resolution"), str) else None,
        )

    def _plan_record(self, plan: MovementDecision) -> dict[str, object]:
        return _compact(
            {
                "planId": plan.id,
                "farmId": plan.farm_id,
                "herdId": plan.herd_id,
                "forDate": _date_to_text(plan.for_date),
                "action": plan.action,
                "reasoning": plan.reasoning,
                "confidence": plan.confidence,
                "sourcePaddockId": plan.source_paddock_id,
                "targetPaddockId": plan.target_paddock_id,
                "knowledgeEntryIds": plan.knowledge_entry_ids,
                "status": plan.status,
                "farmerFeedback": plan.farmer_feedback,
                "createdAt": _datetime_to_text(plan.created_at),
            }
        )

    def _plan_from_record(self, record: object) -> MovementDecision | None:
        if not isinstance(record, dict):
            return None
        return MovementDecision(
            id=str(record["planId"]),
            farm_id=str(record["farmId"]),
            herd_id=record.get("herdId") if isinstance(record.get("herdId"), str) else None,
            for_date=_date_from_text(str(record["forDate"])),
            action=str(record["action"]),  # type: ignore[arg-type]
            reasoning=[str(item) for item in record.get("reasoning", [])],
            confidence=str(record.get("confidence") or "medium"),  # type: ignore[arg-type]
            source_paddock_id=record.get("sourcePaddockId") if isinstance(record.get("sourcePaddockId"), str) else None,
            target_paddock_id=record.get("targetPaddockId") if isinstance(record.get("targetPaddockId"), str) else None,
            knowledge_entry_ids=[str(item) for item in record.get("knowledgeEntryIds", [])],
            status=str(record.get("status") or "pending"),  # type: ignore[arg-type]
            farmer_feedback=record.get("farmerFeedback") if isinstance(record.get("farmerFeedback"), str) else None,
            created_at=_datetime_from_text(str(record["createdAt"])),
        )

    def _brief_record(self, brief: DailyBrief) -> dict[str, object]:
        return _compact(
            {
                "briefId": brief.id,
                "farmId": brief.farm_id,
                "generatedAt": _datetime_to_text(brief.generated_at),
                "summary": brief.summary,
                "recommendationId": brief.recommendation.id,
                "uncertaintyRequest": brief.uncertainty_request,
                "highlights": brief.highlights,
            }
        )

    def list_farms(self) -> list[Farm]:
        records = self._request("farms.list")
        return [farm for item in records or [] if (farm := self._farm_from_record(item))]

    def get_farm(self, farm_id: str) -> Farm | None:
        return self._farm_from_record(self._request("farms.get", {"farmId": farm_id}))

    def create_farm(self, farm: Farm) -> str:
        return str(self._request("farms.create", {"record": self._farm_record(farm)}))

    def update_farm(self, farm_id: str, **updates: object) -> None:
        patch: dict[str, object] = {}
        key_map = {
            "name": "name",
            "timezone": "timezone",
            "herd_ids": "herdIds",
            "notes": "notes",
        }
        for key, value in updates.items():
            if key == "boundary" and isinstance(value, (GeoFeature, GeoPolygon)):
                patch["boundary"] = value.to_geojson()
            elif key == "location" and isinstance(value, GeoPoint):
                patch["location"] = value.to_geojson()
            elif key == "water_sources" and isinstance(value, list):
                patch["waterSources"] = _serialize_water_sources(value)
            elif key in key_map:
                patch[key_map[key]] = value
        if patch:
            self._request("farms.update", {"farmId": farm_id, "patch": patch})

    def get_land_unit(self, land_unit_id: str) -> LandUnit | None:
        return self._land_unit_from_record(self._request("landUnits.get", {"landUnitId": land_unit_id}))

    def list_land_units(self, farm_id: str, unit_type: str | None = None) -> list[LandUnit]:
        args: dict[str, object] = {"farmId": farm_id}
        if unit_type is not None:
            args["unitType"] = unit_type
        records = self._request("landUnits.list", args)
        return [land_unit for item in records or [] if (land_unit := self._land_unit_from_record(item))]

    def upsert_land_unit(self, land_unit: LandUnit) -> str:
        return str(self._request("landUnits.upsert", {"record": self._land_unit_record(land_unit)}))

    def update_land_unit(self, land_unit_id: str, **updates: object) -> None:
        patch: dict[str, object] = {}
        key_map = {
            "parent_id": "parentId",
            "name": "name",
            "area_hectares": "areaHectares",
            "confidence": "confidence",
            "provenance": "provenance",
            "geometry_version": "geometryVersion",
            "status": "status",
            "notes": "notes",
            "warnings": "warnings",
        }
        for key, value in updates.items():
            if key == "geometry" and isinstance(value, GeoFeature):
                patch["geometry"] = value.to_geojson()
            elif key == "updated_at" and isinstance(value, datetime):
                patch["updatedAt"] = _datetime_to_text(value)
            elif key in key_map:
                patch[key_map[key]] = value
        patch.setdefault("updatedAt", _datetime_to_text(datetime.utcnow()))
        self._request("landUnits.update", {"landUnitId": land_unit_id, "patch": patch})

    def create_herd(self, herd: Herd) -> str:
        return str(self._request("herds.create", {"record": self._herd_record(herd)}))

    def get_herds(self, farm_id: str) -> list[Herd]:
        records = self._request("herds.list", {"farmId": farm_id})
        return [herd for item in records or [] if (herd := self._herd_from_record(item))]

    def update_herd_position(self, herd_id: str, paddock_id: str) -> None:
        self._request("herds.updatePosition", {"herdId": herd_id, "paddockId": paddock_id})

    def create_animal(self, animal: Animal) -> str:
        return str(self._request("animals.create", {"record": self._animal_record(animal)}))

    def get_animal(self, animal_id: str) -> Animal | None:
        return self._animal_from_record(self._request("animals.get", {"animalId": animal_id}))

    def list_animals(self, farm_id: str, herd_id: str | None = None) -> list[Animal]:
        args: dict[str, object] = {"farmId": farm_id}
        if herd_id is not None:
            args["herdId"] = herd_id
        records = self._request("animals.list", args)
        return [animal for item in records or [] if (animal := self._animal_from_record(item))]

    def update_animal(self, animal_id: str, **updates: object) -> None:
        patch: dict[str, object] = {}
        key_map = {
            "herd_id": "herdId",
            "species": "species",
            "sex": "sex",
            "name": "name",
            "tag": "tag",
            "secondary_tags": "secondaryTags",
            "breed": "breed",
            "birth_date": "birthDate",
            "dam_id": "damId",
            "sire_id": "sireId",
            "status": "status",
            "current_paddock_id": "currentPaddockId",
            "notes": "notes",
            "metadata": "metadata",
        }
        for key, value in updates.items():
            if key == "updated_at" and isinstance(value, datetime):
                patch["updatedAt"] = _datetime_to_text(value)
            elif key in key_map:
                patch[key_map[key]] = value
        patch.setdefault("updatedAt", _datetime_to_text(datetime.utcnow()))
        self._request("animals.update", {"animalId": animal_id, "patch": patch})

    def record_observation(self, observation: Observation) -> str:
        return str(self._request("observations.record", {"record": self._observation_record(observation)}))

    def record_activity_event(self, event: FarmActivityEvent) -> str:
        return str(self._request("activity.record", {"record": self._activity_record(event)}))

    def list_activity_feed(
        self,
        farm_id: str,
        subject_type: str,
        subject_id: str,
        limit: int = 50,
        before: str | None = None,
    ) -> list[FarmActivityEvent]:
        records = self._request(
            "activity.feed",
            {
                "farmId": farm_id,
                "subjectType": subject_type,
                "subjectId": subject_id,
                "limit": limit,
                "before": before,
            },
        )
        return [event for item in records or [] if (event := self._activity_from_record(item))]

    def list_animal_activity(self, animal_id: str, limit: int = 50) -> list[FarmActivityEvent]:
        records = self._request("activity.byAnimal", {"animalId": animal_id, "limit": limit})
        return [event for item in records or [] if (event := self._activity_from_record(item))]

    def get_recent_observations(self, farm_id: str, days: int = 7) -> list[Observation]:
        observed_after = _datetime_to_text(datetime.utcnow() - timedelta(days=days))
        records = self._request("observations.recent", {"farmId": farm_id, "observedAfter": observed_after})
        return [observation for item in records or [] if (observation := self._observation_from_record(item))]

    def get_paddock_observations(self, paddock_id: str, days: int = 7) -> list[Observation]:
        observed_after = _datetime_to_text(datetime.utcnow() - timedelta(days=days))
        records = self._request("observations.byPaddock", {"paddockId": paddock_id, "observedAfter": observed_after})
        return [observation for item in records or [] if (observation := self._observation_from_record(item))]

    def create_pipeline(self, pipeline: DataPipeline) -> str:
        return str(self._request("pipelines.create", {"record": self._pipeline_record(pipeline)}))

    def get_pipeline(self, pipeline_id: str) -> DataPipeline | None:
        return self._pipeline_from_record(self._request("pipelines.get", {"pipelineId": pipeline_id}))

    def list_pipelines(self, farm_id: str) -> list[DataPipeline]:
        records = self._request("pipelines.list", {"farmId": farm_id})
        return [pipeline for item in records or [] if (pipeline := self._pipeline_from_record(item))]

    def update_pipeline(self, pipeline_id: str, **updates: object) -> None:
        patch: dict[str, object] = {}
        key_map = {
            "name": "name",
            "profile_id": "profileId",
            "login_url": "loginUrl",
            "target_urls": "targetUrls",
            "extraction_prompts": "extractionPrompts",
            "observation_source": "observationSource",
            "observation_tags": "observationTags",
            "schedule": "schedule",
            "vendor_skill_version": "vendorSkillVersion",
            "enabled": "enabled",
            "last_error": "lastError",
        }
        for key, value in updates.items():
            if key == "last_collected_at" and isinstance(value, datetime):
                patch["lastCollectedAt"] = _datetime_to_text(value)
            elif key in key_map:
                patch[key_map[key]] = value
        if patch:
            self._request("pipelines.update", {"pipelineId": pipeline_id, "patch": patch})

    def create_farmer_action(self, action: FarmerAction) -> str:
        return str(self._request("farmerActions.create", {"record": self._farmer_action_record(action)}))

    def list_pending_actions(self, farm_id: str) -> list[FarmerAction]:
        records = self._request("farmerActions.pending", {"farmId": farm_id})
        return [action for item in records or [] if (action := self._farmer_action_from_record(item))]

    def resolve_farmer_action(self, action_id: str, resolution: str) -> None:
        self._request(
            "farmerActions.resolve",
            {"actionId": action_id, "resolvedAt": _datetime_to_text(datetime.utcnow()), "resolution": resolution},
        )

    def create_plan(self, plan: MovementDecision) -> str:
        return str(self._request("plans.create", {"record": self._plan_record(plan)}))

    def get_plan(self, plan_id: str) -> MovementDecision | None:
        return self._plan_from_record(self._request("plans.get", {"planId": plan_id}))

    def get_latest_plan(self, farm_id: str) -> MovementDecision | None:
        return self._plan_from_record(self._request("plans.latest", {"farmId": farm_id}))

    def update_plan_status(self, plan_id: str, status: str, feedback: str | None = None) -> None:
        self._request("plans.updateStatus", {"planId": plan_id, "status": status, "farmerFeedback": feedback})

    def save_daily_brief(self, brief: DailyBrief) -> str:
        return str(self._request("dailyBriefs.save", {"record": self._brief_record(brief)}))

    def get_daily_brief(self, brief_id: str) -> DailyBrief | None:
        record = self._request("dailyBriefs.get", {"briefId": brief_id})
        if not isinstance(record, dict):
            return None
        recommendation = self.get_plan(str(record["recommendationId"]))
        if recommendation is None:
            raise ValueError("Daily brief references a missing recommendation.")
        return DailyBrief(
            id=str(record["briefId"]),
            farm_id=str(record["farmId"]),
            generated_at=_datetime_from_text(str(record["generatedAt"])),
            summary=str(record["summary"]),
            recommendation=recommendation,
            uncertainty_request=record.get("uncertaintyRequest") if isinstance(record.get("uncertaintyRequest"), str) else None,
            highlights=[str(item) for item in record.get("highlights", [])],
        )
