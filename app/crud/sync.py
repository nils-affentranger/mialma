from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.integrations.migadu_client import migadu_client
from app.models.domain import Domain
from app.models.alias import Alias, StagedChange, SyncActionKind
from typing import List, Dict, Any

async def sync_migadu_data(db: AsyncSession):
    # Fetch domains from Migadu
    migadu_domains = await migadu_client.get_domains()
    migadu_domain_names = {d["name"] for d in migadu_domains}
    
    # Identify domains to delete (exist in DB but not in Migadu)
    stmt_all_domains = select(Domain)
    result_all_domains = await db.execute(stmt_all_domains)
    db_domains = result_all_domains.scalars().all()
    
    for db_domain in db_domains:
        if db_domain.name not in migadu_domain_names:
            await db.delete(db_domain)
            
    for d_data in migadu_domains:
        # Update or Create Domain
        domain_name = d_data["name"]
        stmt = select(Domain).where(Domain.name == domain_name)
        result = await db.execute(stmt)
        db_domain = result.scalar_one_or_none()
        
        if db_domain:
            db_domain.description = d_data.get("description")
            db_domain.state = d_data.get("state")
        else:
            db_domain = Domain(
                name=domain_name,
                description=d_data.get("description"),
                state=d_data.get("state")
            )
            db.add(db_domain)
        
        # Fetch aliases for this domain
        migadu_aliases = await migadu_client.get_aliases(domain_name)
        
        # Current aliases in DB for this domain
        stmt_aliases = select(Alias).where(Alias.domain == domain_name)
        result_aliases = await db.execute(stmt_aliases)
        db_aliases = {a.address: a for a in result_aliases.scalars().all()}
        
        for a_data in migadu_aliases:
            address = a_data["address"]
            destinations = a_data.get("destinations", [])
            if isinstance(destinations, list):
                dest_str = ",".join(destinations)
            else:
                dest_str = str(destinations)
                
            if address in db_aliases:
                db_alias = db_aliases[address]
                db_alias.local_part = a_data["local_part"]
                db_alias.destinations = dest_str
            else:
                db_alias = Alias(
                    address=address,
                    local_part=a_data["local_part"],
                    domain=domain_name,
                    destinations=dest_str
                )
                db.add(db_alias)
        
        # We do NOT delete aliases from DB here anymore. 
        # They will be identified as "to_delete" in get_alias_diff 
        # if they exist in DB but not in Migadu.

    await db.commit()


async def get_alias_diff(db: AsyncSession) -> Dict[str, Any]:
    # Fetch all domains from DB
    stmt = select(Domain)
    result = await db.execute(stmt)
    db_domains = result.scalars().all()

    # Fetch staged changes
    stmt_staged = select(StagedChange)
    result_staged = await db.execute(stmt_staged)
    staged_map = {s.address: s.action for s in result_staged.scalars().all()}

    diff = {
        "to_create": [],
        "to_update": [],
        "to_delete": []
    }

    for domain in db_domains:
        domain_name = domain.name
        # Fetch aliases for this domain from Migadu
        migadu_aliases = await migadu_client.get_aliases(domain_name)
        migadu_aliases_map = {a["address"]: a for a in migadu_aliases}

        # Fetch aliases for this domain from DB
        stmt_aliases = select(Alias).where(Alias.domain == domain_name)
        result_aliases = await db.execute(stmt_aliases)
        db_aliases = result_aliases.scalars().all()

        db_alias_addresses = set()
        for db_alias in db_aliases:
            address = db_alias.address
            db_alias_addresses.add(address)
            
            # Prepare local data for comparison
            local_destinations = db_alias.destinations.split(",") if db_alias.destinations else []
            local_destinations.sort()
            
            if address not in migadu_aliases_map:
                # Check if this is an update of an existing alias (local_part changed)
                diff["to_create"].append({
                    "address": address,
                    "domain": domain_name,
                    "local_part": db_alias.local_part,
                    "destinations": local_destinations,
                    "staged": staged_map.get(address) == SyncActionKind.CREATE
                })
            else:
                remote_alias = migadu_aliases_map[address]
                
                # If staged for deletion, add to to_delete
                if staged_map.get(address) == SyncActionKind.DELETE:
                    diff["to_delete"].append({
                        "address": address,
                        "local_part": db_alias.local_part,
                        "domain": domain_name,
                        "staged": True
                    })
                    continue

                remote_destinations = remote_alias.get("destinations", [])
                if not isinstance(remote_destinations, list):
                    remote_destinations = [remote_destinations]
                remote_destinations.sort()
                
                if (local_destinations != remote_destinations):
                    diff["to_update"].append({
                        "address": address,
                        "domain": domain_name,
                        "local_part": db_alias.local_part,
                        "destinations": local_destinations,
                        "old_destinations": remote_destinations,
                        "staged": staged_map.get(address) == SyncActionKind.UPDATE
                    })
        
        # Check for aliases on Migadu that are not in DB
        for address, remote_alias in migadu_aliases_map.items():
            if address not in db_alias_addresses:
                # Potential rename detection
                # Check if any to_create has the same domain and NOT already matched
                matched_as_rename = False
                for i, create_item in enumerate(diff["to_create"]):
                    if (create_item["domain"] == domain_name and 
                        create_item.get("rename_from") is None):
                        
                        remote_destinations = remote_alias.get("destinations", [])
                        if not isinstance(remote_destinations, list):
                            remote_destinations = [remote_destinations]
                        remote_destinations.sort()
                        
                        # If destinations match, we'll call it an update (rename)
                        # To avoid matching new aliases as renames of unrelated aliases,
                        # we prefer if the new address is explicitly staged as UPDATE.
                        # However, if it's NOT staged yet, we can still match it as a potential rename
                        # to show it correctly in the diff.
                        is_explicit_update = staged_map.get(create_item["address"]) == SyncActionKind.UPDATE
                        is_not_staged = create_item["address"] not in staged_map
                        
                        if ((is_explicit_update or is_not_staged) and 
                            create_item["destinations"] == remote_destinations):
                            
                            # Move from to_create to to_update
                            create_item["address"] = create_item["address"] # New address
                            create_item["old_address"] = address
                            create_item["old_local_part"] = remote_alias["local_part"]
                            create_item["old_destinations"] = remote_destinations
                            # Update staged status - if either new or old is staged for update?
                            # Usually if it's a rename, user would stage the NEW address as CREATE or UPDATE?
                            # The UI probably shows the new one.
                            
                            diff["to_update"].append(create_item)
                            # Update staged status
                            create_item["staged"] = staged_map.get(create_item["address"]) == SyncActionKind.UPDATE or staged_map.get(create_item["address"]) == SyncActionKind.CREATE
                            
                            diff["to_create"].pop(i)
                            matched_as_rename = True
                            break
                
                if not matched_as_rename:
                    # Only add to to_delete if the remote alias is NOT in DB.
                    # This should already be true because of 'if address not in db_alias_addresses'
                    diff["to_delete"].append({
                        "address": address,
                        "local_part": remote_alias["local_part"],
                        "domain": domain_name,
                        "staged": staged_map.get(address) == SyncActionKind.DELETE
                    })
                
    return diff


async def push_alias_diff(db: AsyncSession) -> Dict[str, Any]:
    diff = await get_alias_diff(db)
    pushed = {
        "to_create": [],
        "to_update": [],
        "to_delete": []
    }
    
    for item in diff["to_create"]:
        if item["staged"]:
            await migadu_client.create_alias(
                domain=item["domain"],
                local_part=item["local_part"],
                destinations=item["destinations"]
            )
            pushed["to_create"].append(item)
            staged = await db.get(StagedChange, item["address"])
            if staged:
                await db.delete(staged)
        
    for item in diff["to_update"]:
        if item["staged"]:
            if "old_address" in item:
                # This is a rename. Migadu supports renaming local_part via PUT.
                await migadu_client.update_alias(
                    domain=item["domain"],
                    local_part=item["old_local_part"],
                    new_local_part=item["local_part"],
                    destinations=item["destinations"]
                )
            else:
                await migadu_client.update_alias(
                    domain=item["domain"],
                    local_part=item["local_part"],
                    destinations=item["destinations"]
                )
            pushed["to_update"].append(item)
            staged = await db.get(StagedChange, item["address"])
            if staged:
                await db.delete(staged)
        
    for item in diff["to_delete"]:
        if item["staged"]:
            await migadu_client.delete_alias(
                domain=item["domain"],
                local_part=item["local_part"]
            )
            pushed["to_delete"].append(item)
            
            # Remove from staged
            staged = await db.get(StagedChange, item["address"])
            if staged:
                await db.delete(staged)
                
            # ALSO remove from local database if it exists
            stmt_alias = select(Alias).where(Alias.address == item["address"])
            result_alias = await db.execute(stmt_alias)
            db_alias = result_alias.scalar_one_or_none()
            if db_alias:
                await db.delete(db_alias)
        
    await db.commit()
    return pushed


async def stage_alias_change(db: AsyncSession, domain: str, local_part: str, action: SyncActionKind):
    address = f"{local_part}@{domain}"
    stmt = select(StagedChange).where(StagedChange.address == address)
    result = await db.execute(stmt)
    staged = result.scalar_one_or_none()
    
    if staged:
        staged.action = action
    else:
        staged = StagedChange(address=address, action=action)
        db.add(staged)
    await db.commit()


async def stage_all_changes(db: AsyncSession):
    diff = await get_alias_diff(db)
    
    for item in diff["to_create"]:
        address = item["address"]
        stmt = select(StagedChange).where(StagedChange.address == address)
        result = await db.execute(stmt)
        staged = result.scalar_one_or_none()
        if not staged:
            db.add(StagedChange(address=address, action=SyncActionKind.CREATE))
            
    for item in diff["to_update"]:
        address = item["address"]
        stmt = select(StagedChange).where(StagedChange.address == address)
        result = await db.execute(stmt)
        staged = result.scalar_one_or_none()
        if not staged:
            db.add(StagedChange(address=address, action=SyncActionKind.UPDATE))
            
    for item in diff["to_delete"]:
        address = item["address"]
        stmt = select(StagedChange).where(StagedChange.address == address)
        result = await db.execute(stmt)
        staged = result.scalar_one_or_none()
        if not staged:
            db.add(StagedChange(address=address, action=SyncActionKind.DELETE))
            
    await db.commit()


async def discard_all_changes(db: AsyncSession):
    diff = await get_alias_diff(db)
    
    for item in diff["to_create"]:
        await discard_alias_change(db, item["domain"], item["local_part"], SyncActionKind.CREATE)
        
    for item in diff["to_update"]:
        await discard_alias_change(db, item["domain"], item["local_part"], SyncActionKind.UPDATE)
        
    for item in diff["to_delete"]:
        await discard_alias_change(db, item["domain"], item["local_part"], SyncActionKind.DELETE)
    
    await db.commit()


async def discard_alias_change(db: AsyncSession, domain: str, local_part: str, action: SyncActionKind):
    address = f"{local_part}@{domain}"
    # Remove from staged if present
    stmt = select(StagedChange).where(StagedChange.address == address)
    result = await db.execute(stmt)
    staged = result.scalar_one_or_none()
    if staged:
        await db.delete(staged)

    if action == SyncActionKind.CREATE:
        # Created in DB but not in Migadu. Discard means delete from DB.
        stmt_alias = select(Alias).where(Alias.address == address)
        result_alias = await db.execute(stmt_alias)
        db_alias = result_alias.scalar_one_or_none()
        if db_alias:
            await db.delete(db_alias)
            
    elif action == SyncActionKind.UPDATE or action == SyncActionKind.DELETE:
        # Revert to remote state
        domain_name = address.split("@")[1]
        remote_aliases = await migadu_client.get_aliases(domain_name)
        remote_alias = next((a for a in remote_aliases if a["address"] == address), None)
        
        if remote_alias:
            destinations = remote_alias.get("destinations", [])
            dest_str = ",".join(destinations) if isinstance(destinations, list) else str(destinations)
            
            stmt_alias = select(Alias).where(Alias.address == address)
            result_alias = await db.execute(stmt_alias)
            db_alias = result_alias.scalar_one_or_none()
            
            if db_alias:
                db_alias.local_part = remote_alias["local_part"]
                db_alias.destinations = dest_str
            else:
                db_alias = Alias(
                    address=address,
                    local_part=remote_alias["local_part"],
                    domain=domain_name,
                    destinations=dest_str
                )
                db.add(db_alias)
        else:
            # If it's not on Migadu, it should be deleted from DB (if it exists)
            stmt_alias = select(Alias).where(Alias.address == address)
            result_alias = await db.execute(stmt_alias)
            db_alias = result_alias.scalar_one_or_none()
            if db_alias:
                await db.delete(db_alias)

    await db.commit()
