"""Base repository class for common database operations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime
import json

from .database_manager import DatabaseManager


class BaseRepository(ABC):
    """Base repository class with common database operations."""
    
    def __init__(self, db_manager: DatabaseManager, table_name: str):
        """
        Initialize repository.
        
        Args:
            db_manager: Database manager instance
            table_name: Name of the table this repository manages
        """
        self.db_manager = db_manager
        self.table_name = table_name
    
    def _serialize_value(self, value: Any) -> str:
        """Serialize complex values to JSON string."""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        elif isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, bool):
            return str(int(value))
        return str(value) if value is not None else None
    
    def _deserialize_value(self, value: str, target_type: type = str) -> Any:
        """Deserialize JSON string back to original type."""
        if value is None:
            return None
            
        if target_type == dict or target_type == list:
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return {} if target_type == dict else []
        elif target_type == bool:
            return bool(int(value)) if value.isdigit() else bool(value)
        elif target_type == int:
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
        elif target_type == float:
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0
        elif target_type == datetime:
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        
        return value
    
    def _build_where_clause(self, conditions: Dict[str, Any]) -> Tuple[str, tuple]:
        """
        Build WHERE clause from conditions dictionary.
        
        Args:
            conditions: Dictionary of field:value conditions
            
        Returns:
            Tuple of (where_clause, params)
        """
        if not conditions:
            return "", ()
        
        where_parts = []
        params = []
        
        for key, value in conditions.items():
            if value is None:
                where_parts.append(f"{key} IS NULL")
            elif isinstance(value, (list, tuple)):
                placeholders = ",".join(["?" for _ in value])
                where_parts.append(f"{key} IN ({placeholders})")
                params.extend(value)
            else:
                where_parts.append(f"{key} = ?")
                params.append(value)
        
        where_clause = " AND ".join(where_parts)
        return f"WHERE {where_clause}" if where_clause else "", tuple(params)
    
    def find_by_id(self, id_value: Union[str, int]) -> Optional[Dict[str, Any]]:
        """
        Find record by primary key.
        
        Args:
            id_value: Primary key value
            
        Returns:
            Record dictionary or None
        """
        # Try common primary key field names
        pk_fields = ['id', f'{self.table_name[:-1]}_id', 'chat_id', 'user_id']
        
        for pk_field in pk_fields:
            try:
                query = f"SELECT * FROM {self.table_name} WHERE {pk_field} = ? LIMIT 1"
                result = self.db_manager.execute_query(query, (id_value,))
                if result:
                    return dict(result[0])
            except Exception:
                continue
        
        return None
    
    def find_all(self, conditions: Dict[str, Any] = None, 
                 order_by: str = None, limit: int = None) -> List[Dict[str, Any]]:
        """
        Find all records matching conditions.
        
        Args:
            conditions: Filter conditions
            order_by: ORDER BY clause
            limit: LIMIT clause
            
        Returns:
            List of record dictionaries
        """
        query = f"SELECT * FROM {self.table_name}"
        params = ()
        
        if conditions:
            where_clause, params = self._build_where_clause(conditions)
            query += f" {where_clause}"
        
        if order_by:
            query += f" ORDER BY {order_by}"
        
        if limit:
            query += f" LIMIT {limit}"
        
        result = self.db_manager.execute_query(query, params)
        return [dict(row) for row in result]
    
    def find_one(self, conditions: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find one record matching conditions.
        
        Args:
            conditions: Filter conditions
            
        Returns:
            Record dictionary or None
        """
        results = self.find_all(conditions, limit=1)
        return results[0] if results else None
    
    def count(self, conditions: Dict[str, Any] = None) -> int:
        """
        Count records matching conditions.
        
        Args:
            conditions: Filter conditions
            
        Returns:
            Count of matching records
        """
        query = f"SELECT COUNT(*) as count FROM {self.table_name}"
        params = ()
        
        if conditions:
            where_clause, params = self._build_where_clause(conditions)
            query += f" {where_clause}"
        
        result = self.db_manager.execute_query(query, params)
        return result[0]['count'] if result else 0
    
    def insert(self, data: Dict[str, Any]) -> Optional[int]:
        """
        Insert a new record.
        
        Args:
            data: Record data dictionary
            
        Returns:
            Inserted record ID or None
        """
        if not data:
            return None
        
        # Add timestamps
        if 'created_at' not in data:
            data['created_at'] = datetime.now().isoformat()
        if 'updated_at' not in data:
            data['updated_at'] = datetime.now().isoformat()
        
        fields = list(data.keys())
        placeholders = ",".join(["?" for _ in fields])
        values = [self._serialize_value(data[field]) for field in fields]
        
        query = f"INSERT INTO {self.table_name} ({','.join(fields)}) VALUES ({placeholders})"
        
        try:
            with self.db_manager.get_transaction() as conn:
                cursor = conn.execute(query, values)
                return cursor.lastrowid
        except Exception as e:
            raise Exception(f"Insert failed: {e}")
    
    def insert_many(self, data_list: List[Dict[str, Any]]) -> int:
        """
        Insert multiple records.
        
        Args:
            data_list: List of record data dictionaries
            
        Returns:
            Number of inserted records
        """
        if not data_list:
            return 0
        
        # Add timestamps to all records
        for data in data_list:
            if 'created_at' not in data:
                data['created_at'] = datetime.now().isoformat()
            if 'updated_at' not in data:
                data['updated_at'] = datetime.now().isoformat()
        
        # Use fields from first record
        fields = list(data_list[0].keys())
        placeholders = ",".join(["?" for _ in fields])
        
        query = f"INSERT INTO {self.table_name} ({','.join(fields)}) VALUES ({placeholders})"
        
        params_list = []
        for data in data_list:
            values = [self._serialize_value(data.get(field)) for field in fields]
            params_list.append(values)
        
        return self.db_manager.execute_many(query, params_list)
    
    def update(self, conditions: Dict[str, Any], data: Dict[str, Any]) -> int:
        """
        Update records matching conditions.
        
        Args:
            conditions: Update conditions
            data: New data
            
        Returns:
            Number of updated records
        """
        if not conditions or not data:
            return 0
        
        # Add updated timestamp
        data['updated_at'] = datetime.now().isoformat()
        
        set_parts = [f"{key} = ?" for key in data.keys()]
        set_clause = ",".join(set_parts)
        set_params = [self._serialize_value(value) for value in data.values()]
        
        where_clause, where_params = self._build_where_clause(conditions)
        
        query = f"UPDATE {self.table_name} SET {set_clause} {where_clause}"
        params = set_params + list(where_params)
        
        return self.db_manager.execute_query(query, tuple(params), fetch=False)
    
    def delete(self, conditions: Dict[str, Any]) -> int:
        """
        Delete records matching conditions.
        
        Args:
            conditions: Delete conditions
            
        Returns:
            Number of deleted records
        """
        if not conditions:
            return 0  # Safety: don't delete all records
        
        where_clause, params = self._build_where_clause(conditions)
        
        if not where_clause:
            return 0  # Safety: don't delete all records
        
        query = f"DELETE FROM {self.table_name} {where_clause}"
        
        return self.db_manager.execute_query(query, params, fetch=False)
    
    def upsert(self, unique_fields: List[str], data: Dict[str, Any]) -> Optional[int]:
        """
        Insert or update record based on unique fields.
        
        Args:
            unique_fields: List of fields that make record unique
            data: Record data
            
        Returns:
            Record ID or None
        """
        # Check if record exists
        conditions = {field: data[field] for field in unique_fields if field in data}
        existing = self.find_one(conditions)
        
        if existing:
            # Update existing record
            self.update(conditions, data)
            return existing.get('id')
        else:
            # Insert new record
            return self.insert(data)
    
    def execute_custom_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Execute custom query.
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            Query results
        """
        result = self.db_manager.execute_query(query, params)
        return [dict(row) for row in result] if result else []